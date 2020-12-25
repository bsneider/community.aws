#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Brian Felton <github: bjfelton>
#  - Brandon Sneider <github: bsneider>
#
# apigw_api_key
#    Manage creation, update, and removal of API Gateway ApiKey resources
#
# NOTE: While it is possible via the boto api to update the ApiKey's name,
#       this module does not support this functionality since it searches
#       for the ApiKey's id by its name.

# MIT License
#
# Copyright (c) 2016 Brian Felton, Emerson
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type

DOCUMENTATION = '''
module: apigw_api_key
author: Brian Felton (@bjfelton)
short_description: Add, update, or remove ApiKey resources
description:
  - Create if no ApiKey resource is found matching the provided name
  - Delete ApiKey resource matching the provided name
  - Updates I(enabled) and I(description)
version_added: "2.2"
options:
  name:
    description:
    - The domain name of the ApiKey resource on which to operate
    type: string
    required: True
  value:
    description:
    - Value of the api key. Required for create.
    type: string
    default: None
    required: False
  description:
    description:
    - ApiKey description
    type: string
    default: None
    required: False
  enabled:
    description:
    - Can ApiKey be used by called
    type: bool
    default: False
    required: False
  generate_distinct_id:
    description:
    - Specifies whether key identifier is distinct from created apikey value
    type: bool
    default: False
    required: False
  state:
    description:
    - Should api_key exist or not
    choices: ['present', 'absent']
    default: 'present'
    required: False
requirements:
    - python = 2.7
    - boto
    - boto3
notes:
    - While it is possible via the boto api to update the ApiKey's name, this module does not support this functionality since it searches for the ApiKey's id by its name.
    - This module requires that you have boto and boto3 installed and that your credentials are created or stored in a way that is compatible (see U(https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration)).
'''

EXAMPLES = '''
---
- hosts: localhost
  gather_facts: False
  tasks:
  - name: api key creation
    apigw_api_key:
      name: testkey5000
      description: 'this is an awesome test'
      enabled: True
      value: 'notthegreatestkeyintheworld:justatribute'
      state: present
    register: apikey

  - debug: var=apikey
'''

RETURN = '''
{
  "apikey": {
    "api_key": {
      "ResponseMetadata": {
        "HTTPHeaders": {
          "content-length": "216",
          "content-type": "application/json",
          "date": "Tue, 13 Dec 2016 03:45:35 GMT",
        },
        "HTTPStatusCode": 201,
        "RetryAttempts": 0
      },
      "createdDate": "2016-12-12T21:45:35-06:00",
      "description": "this is an awesome test",
      "enabled": true,
      "id": "24601abcde",
      "lastUpdatedDate": "2016-12-12T21:45:35-06:00",
      "name": "testkey5000",
      "stageKeys": [],
      "value": "notthegreatestkeyintheworld:justatribute"
    },
    "changed": true
  }
}
'''

__version__ = '${version}'

try:
    import boto
    import boto3
    from botocore.exceptions import BotoCoreError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class ApiGwApiKey:
    def __init__(self, module):
        """
        Constructor
        """
        self.module = module
        if (not HAS_BOTO3):
            self.module.fail_json(
                msg="boto and boto3 are required for this module")
        self.client = boto3.client('apigateway')

    @staticmethod
    def _define_module_argument_spec():
        """
        Defines the module's argument spec
        :return: Dictionary defining module arguments
        """
        return dict(name=dict(required=True),
                    description=dict(required=False),
                    value=dict(required=False),
                    enabled=dict(required=False, type='bool', default=False),
                    generate_distinct_id=dict(
            required=False, type='bool', default=False),
            state=dict(default='present', choices=[
                'present', 'absent']),
        )

    def _retrieve_api_key(self):
        """
        Retrieve all api_keys in the account and match them against the provided name
        :return: Result matching the provided api name or an empty hash
        """
        resp = None
        try:
            get_resp = self.client.get_api_keys(
                nameQuery=self.module.params['name'], includeValues=True)

            for item in get_resp.get('items', []):
                if item['name'] == self.module.params.get('name'):
                    resp = item
        except BotoCoreError as e:
            self.module.fail_json(
                msg="Error when getting api_keys from boto3: {}".format(e))

        return resp

    def _delete_api_key(self):
        """
        Delete api_key that matches the returned id
        :return: True
        """
        try:
            if not self.module.check_mode:
                self.client.delete_api_key(apiKey=self.me['id'])
            return True
        except BotoCoreError as e:
            self.module.fail_json(
                msg="Error when deleting api_key via boto3: {}".format(e))

    def _create_api_key(self):
        """
        Create api_key from provided args
        :return: True, result from create_api_key
        """
        api_key = None
        changed = False

        try:
            changed = True
            if not self.module.check_mode:
                args = dict(
                    name=self.module.params['name'],
                    enabled=self.module.params.get('enabled', False),
                    generateDistinctId=self.module.params.get(
                        'generate_distinct_id', False),
                )

                for opt_field in ['description', 'value']:
                    if self.module.params.get(opt_field, None) not in [None, '']:
                        args[opt_field] = self.module.params[opt_field]

                api_key = self.client.create_api_key(**args)
        except BotoCoreError as e:
            self.module.fail_json(
                msg="Error when creating api_key via boto3: {}".format(e))

        return (changed, api_key)

    @staticmethod
    def _create_patches(params, me):
        patches = []

        for param in ['enabled', 'description']:
            ans_value = params.get(param, None)
            if ans_value is not None and (param not in me or str(ans_value) != str(me[param])):
                # More special snowflake logic because boto removes description
                # from get results if the key is set to empty string
                if param == 'description' and ans_value == '' and param not in me:
                    pass
                else:
                    patches.append(
                        {'op': 'replace', 'path': "/{}".format(param), 'value': str(ans_value)})

        return patches

    def _update_api_key(self):
        """
        Create api_key from provided args
        :return: True, result from create_api_key
        """
        api_key = self.me
        changed = False

        try:
            patches = ApiGwApiKey._create_patches(self.module.params, self.me)
            if patches:
                changed = True

                if not self.module.check_mode:
                    self.client.update_api_key(
                        apiKey=self.me['id'],
                        patchOperations=patches
                    )
                    api_key = self._retrieve_api_key()
        except BotoCoreError as e:
            self.module.fail_json(
                msg="Error when updating api_key via boto3: {}".format(e))

        return (changed, api_key)

    def process_request(self):
        """
        Process the user's request -- the primary code path
        :return: Returns either fail_json or exit_json
        """

        api_key = None
        changed = False
        self.me = self._retrieve_api_key()

        if self.module.params.get('state', 'present') == 'absent' and self.me is not None:
            changed = self._delete_api_key()
        elif self.module.params.get('state', 'present') == 'present':
            if self.me is None:
                (changed, api_key) = self._create_api_key()
            else:
                (changed, api_key) = self._update_api_key()

        self.module.exit_json(changed=changed, api_key=api_key)


def main():
    """
    Instantiates the module and calls process_request.
    :return: none
    """
    module = AnsibleModule(
        argument_spec=ApiGwApiKey._define_module_argument_spec(),
        supports_check_mode=True
    )

    api_key = ApiGwApiKey(module)
    api_key.process_request()


if __name__ == '__main__':
    main()
