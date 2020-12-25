#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Jarrod McEvers     <github: JarrodAMcEvers>
#  - Brandon Sneider <github: bsneider>
#
# apigw_model
#    Manage creation, update, and removal of API Gateway Models.
#

# MIT License
#
# Copyright (c) 2019 Jarrod McEvers, Emerson
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
module: apigw_model
authors: Jarrod McEvers (@JarrodAMcEvers)
short_description: Add, update, or remove AWS API Gateway Models.
description:
- Create, Update, and Delete operations for Models
version_added: "2.4"
options:
  rest_api_id:
    description:
    - The id of the parent rest api.
    type: 'string'
    required: True
  name:
    description:
    - The name of the model on which to operate.
    type: 'string'
    required: True
  content_type:
    description:
    - The content-type for the model. This is required if state is present.
    type: 'string'
    required: False
  schema:
    description:
    - The schema for the model. This is required if state is present. If content_type is application/json, this should be a JSON schema draft 4 model.
    type: 'string'
    required: False
  description:
    description:
    - The description for the model.
    type: 'string'
    default: ''
    required: False
  state:
    description:
    - Determine whether to assert if model should exist or not.
    type: 'string'
    choices: ['present', 'absent']
    default: 'present'
    required: False

requirements:
    - python = 2.7
    - boto
    - boto3
notes:
- Even though the docs say that schema is not required for create model, it seems that it is actually required.
- This module requires that you have boto and boto3 installed and that your credentials are created or stored in a way that is compatible (see U(https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration)).
'''

EXAMPLES = '''
- name: Test playbook for creating API GW Models
  hosts: localhost
  gather_facts: False
  tasks:
    - name: Create an api
      apigw_rest_api:
        name: 'my.example.com'
        state: present
      register: restapi

    - name: Create a resource
      apigw_model:
        rest_api_id: "{{ restapi.api.id }}"
        name: 'Model'
        content_type: 'application/pdf'
        schema: '{}'
        state: 'present'
'''

RETURN = '''
Response after create
{
    "model": {
        "name": "Model",
        "contentType": "application/pdf",
        "id": "some_model_id",
        "ResponseMetadata": {
            "RetryAttempts": 0,
            "HTTPStatusCode": 201,
            "RequestId": "77777777-7777-7777-7777-77777777777",
            "HTTPHeaders": {
                "x-amzn-requestid": "77777777-7777-7777-7777-77777777777",
                "content-length": "77",
                "x-amz-apigw-id": "some_id",
                "connection": "keep-alive",
                "date": "Thu, 29 Aug 2019 16:18:20 GMT",
                "content-type": "application/json"
            }
        },
        "schema": "{}"
    }
}
'''


try:
    import boto
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class ApiGwModel:
    def __init__(self, module):
        self.module = module
        if (not HAS_BOTO3):
            self.module.fail_json(
                msg="boto and boto3 are required for this module")
        self.client = boto3.client('apigateway')

    @staticmethod
    def _define_module_argument_spec():
        return dict(
            rest_api_id=dict(required=True, type='str'),
            name=dict(required=True, type='str'),
            content_type=dict(required=False, type='str'),
            schema=dict(required=False, type='str'),
            description=dict(required=False, type='str', default=''),
            state=dict(default='present', choices=['present', 'absent'])
        )

    def _find_model(self):
        try:
            return self.client.get_model(
                restApiId=self.module.params.get('rest_api_id'),
                modelName=self.module.params.get('name'),
                flatten=True
            )
        except ClientError:
            return None

    def _delete_model(self):
        if not self.module.check_mode:
            try:
                self.client.delete_model(
                    restApiId=self.module.params.get('rest_api_id'),
                    modelName=self.module.params.get('name')
                )
            except ClientError as e:
                if 'NotFoundException' in e.message:
                    return None
                self.module.fail_json(
                    msg='Error while deleting model: {}'.format(e))

        return None

    def _patch_builder(self):
        return [
            dict(
                op='replace',
                path='/schema',
                value=self.module.params.get('schema')
            ),
            dict(
                op='replace',
                path='/description',
                value=self.module.params.get('description')
            )
        ]

    def _update_model(self):
        description = self.model.get('description', None)
        moduleDescription = self.module.params.get('description', None)

        if self.module.params.get('schema') == self.model['schema'] and description == moduleDescription:
            return False, None

        if self.module.check_mode:
            return True, None
        try:
            patches = self._patch_builder()
            response = self.client.update_model(
                restApiId=self.module.params.get('rest_api_id'),
                modelName=self.module.params.get('name'),
                patchOperations=patches
            )
            return True, response
        except ClientError as e:
            self.module.fail_json(
                msg='Error while updating model: {}'.format(e))

    def _create_model(self):
        if self.module.check_mode:
            return True, None

        args = dict(
            restApiId=self.module.params.get('rest_api_id'),
            name=self.module.params.get('name'),
            contentType=self.module.params.get('content_type'),
            schema=self.module.params.get('schema'),
            description=self.module.params.get('description')
        )

        try:
            response = self.client.create_model(**args)
            return True, response
        except ClientError as e:
            self.module.fail_json(
                msg='Error while creating model: {}'.format(e))

    def process_request(self):
        changed = False
        response = None

        self.model = self._find_model()

        if self.module.params.get('state') == 'absent' and self.model == None:
            changed = False
        elif self.module.params.get('state') == 'absent':
            self._delete_model()
            changed = True
        elif self.model == None:
            changed, response = self._create_model()
        else:
            changed, response = self._update_model()

        self.module.exit_json(changed=changed, model=response)


def main():
    module = AnsibleModule(
        argument_spec=ApiGwModel._define_module_argument_spec(),
        supports_check_mode=True
    )
    model = ApiGwModel(module)
    model.process_request()


if __name__ == '__main__':
    main()
