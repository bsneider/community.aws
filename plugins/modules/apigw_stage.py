#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Brian Felton <github: bjfelton>
#  - Brandon Sneider <github: bsneider>
#
# apigw_stage
#    Update or remove API Gateway Stage resources
#    Only processes 'replace' patches.
#

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

import re
from json import dumps

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type


DOCUMENTATION = '''
module: apigw_stage
author: Brian Felton (@bjfelton)
short_description: An Ansible module to update or remove an apigateway Stage
description:
- Updates or removes API Gateway Stage resources
- Only processes 'replace' patches for updates
version_added: "2.2"
options:
  name:
    description:
    - The name of the stage to deploy
    type: 'string'
    required: True
    aliases: ['stage_name']
  rest_api_id:
    description:
    - The id of the parent rest api
    type: 'string'
    required: True
  description:
    description:
    - The description for the Stage resource to create
    type: 'string'
    default: None
    required: False
  cache_cluster_enabled:
    description:
    - Cache cluster setting for the Stage resource
    type: 'bool'
    default: None
    required: False
  cache_cluster_size:
    description:
    - Specifies the size of the cache cluster for the Stage resource
    type: 'string'
    default: None
    choices: ['0.5','1.6','6.1','13.5','28.4','58.2','118','237']
    required: False
  method_settings:
    description:
    - List of dictionaries capturing methods to be patched
    type: 'list'
    default: []
    required: False
    options:
      method_name:
        description:
        - Name of the method to be patched
        type: 'string'
        required: True
      method_verb:
        description:
        - Verb of the method to be patched
        type: 'string'
        choices: ['GET', 'PUT', 'POST', 'DELETE', 'HEAD', 'PATCH', 'OPTIONS']
        required: True
      caching_enabled:
        description:
        - Flag indicating if caching should be enabled
        type: 'bool'
        default: False
        required: False
  state:
    description:
    - State of the stage resource
    type: 'string'
    default: 'present'
    choices: ['present', 'absent']
    required: False

requirements:
    - python = 2.7
    - boto
    - boto3
notes:
    - This module does not currently create stages, as these are a byproduct of executing deployments.
    - This module requires that you have boto and boto3 installed and that your credentials are created or stored in a way that is compatible (see U(https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration)).
'''

EXAMPLES = '''
- name: Test playbook for creating API GW Method resource
  hosts: localhost
  gather_facts: False
  tasks:
    - name: stage updatin'
      apigw_stage:
        rest_api_id: your_api_id
        name: dev
        description: 'This is a test of the emergency deployment system'
        method_settings:
          - method_name: /test
            method_verb: PUT
            caching_enabled: False
      register: stage

    - debug: var=stage
'''

RETURN = '''
{
  "stage": {
    "changed": true,
    "stage": {
      "ResponseMetadata": {
        "HTTPHeaders": {
          "content-length": "10449",
          "content-type": "application/json",
          "date": "Tue, 29 Nov 2016 14:31:48 GMT",
          "x-amzn-requestid": "request id"
        },
        "HTTPStatusCode": 200,
        "RequestId": "request id",
        "RetryAttempts": 0
      },
      "cacheClusterEnabled": true,
      "cacheClusterSize": "0.5",
      "cacheClusterStatus": "AVAILABLE",
      "createdDate": "2016-09-09T10:41:03-05:00",
      "deploymentId": "7vvkyf",
      "description": "This is a test of the emergency deployment system",
      "lastUpdatedDate": "2016-11-29T08:31:46-06:00",
      "methodSettings": {
        "*/*": {
          "cacheDataEncrypted": false,
          "cacheTtlInSeconds": 600,
          "cachingEnabled": true,
          "dataTraceEnabled": true,
          "loggingLevel": "INFO",
          "metricsEnabled": true,
          "requireAuthorizationForCacheControl": false,
          "throttlingBurstLimit": -1,
          "throttlingRateLimit": -1.0,
          "unauthorizedCacheControlHeaderStrategy": "SUCCEED_WITH_RESPONSE_HEADER"
        },
        "~1test/PUT": {
          "cacheDataEncrypted": false,
          "cacheTtlInSeconds": 600,
          "cachingEnabled": false,
          "dataTraceEnabled": true,
          "loggingLevel": "INFO",
          "metricsEnabled": true,
          "requireAuthorizationForCacheControl": false,
          "throttlingBurstLimit": -1,
          "throttlingRateLimit": -1.0,
          "unauthorizedCacheControlHeaderStrategy": "SUCCEED_WITH_RESPONSE_HEADER"
        },
      },
      "stageName": "dev"
    }
  }
}
'''

__version__ = '${version}'


try:
    import boto
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def create_patch(path, value):
    return {'op': 'replace', 'path': "/{}".format(path), 'value': str(value)}


def build_patch_args(stage, params):
    args = None

    arg_map = {
        'description': 'description',
        'cache_cluster_enabled': 'cacheClusterEnabled',
        'cache_cluster_size': 'cacheClusterSize',
    }

    stage = {} if stage is None else stage
    stg_methods = stage.get('methodSettings', {})

    patches = []
    for ans_param, boto_param in arg_map.items():
        if ans_param in params and params[ans_param] is not None:
            if boto_param in stage and str(params[ans_param]) == str(stage[boto_param]):
                pass
            else:
                patches.append(create_patch(boto_param, params[ans_param]))
        else:
            # To avoid unnecessary changes and complexity, I am punting on attempting
            # to resolve discrepancies between existing Stage values and parameters
            # that the user has not provided.  This may create an edge case somewhere,
            # but it seems overall safer than potentially hosing up cache settings
            # for the entire Stage.
            pass

    for m in params.get('method_settings', []):
        method_key = "{0}/{1}".format(re.sub('/',
                                             '~1', m['method_name']), m['method_verb'])

        if method_key not in stg_methods or str(stg_methods[method_key]['cachingEnabled']) != str(m.get('caching_enabled', False)):
            patches.append(create_patch(
                "{}/caching/enabled".format(method_key), m.get('caching_enabled', False)))

    if patches:
        args = {
            'restApiId': params['rest_api_id'],
            'stageName': params['name'],
            'patchOperations': patches
        }

    return args


class ApiGwStage:
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
        return dict(name=dict(required=True, aliases=['stage_name']),
                    rest_api_id=dict(required=True),
                    description=dict(required=False),
                    cache_cluster_enabled=dict(required=False, type='bool'),
                    cache_cluster_size=dict(required=False, choices=[
                                            '0.5', '1.6', '6.1', '13.5', '28.4', '58.2', '118', '237']),
                    method_settings=dict(
            required=False,
            default=[],
            type='list',
            method_name=dict(required=True),
            method_verb=dict(required=True, choices=[
                             'GET', 'PUT', 'POST', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH']),
            caching_enabled=dict(required=False, default=False, type='bool')
        ),
            state=dict(required=False, default='present',
                       choices=['absent', 'present'])
        )

    def _find_stage(self):
        """
        Attempts to find the stage
        :return: Returns boolean indicating whether api has been called.  Calls fail_json
                 on error
        """
        try:
            return self.client.get_stage(
                restApiId=self.module.params.get('rest_api_id'),
                stageName=self.module.params.get('name')
            )
        except ClientError as e:
            if 'NotFoundException' in dumps(e.response):
                return None
            else:
                self.module.fail_json(
                    msg='Error while finding stage via boto3: {}'.format(e))
        except BotoCoreError as e:
            self.module.fail_json(
                msg='Error while finding stage via boto3: {}'.format(e))

    def _delete_stage(self):
        """
        Delete the stage
        :return: Returns boolean indicating whether api has been called.  Calls fail_json
                 on error
        """
        changed = False

        if not self.module.check_mode:
            try:
                changed = True
                self.client.delete_stage(
                    restApiId=self.module.params.get('rest_api_id'),
                    stageName=self.module.params.get('name')
                )
            except BotoCoreError as e:
                self.module.fail_json(
                    msg="Error while deleting stage via boto3: {}".format(e))

        return changed

    def _update_stage(self):
        """
        Update the stage
        :return:
          changed - boolean indicating whether a change has occurred
          result  - results of a find after a change has occurred
        """
        changed = False
        result = None

        patch_args = build_patch_args(self.stage, self.module.params)

        try:
            if patch_args is not None:
                changed = True
                if not self.module.check_mode:
                    self.client.update_stage(**patch_args)
                    result = self.client.get_stage(
                        restApiId=self.module.params.get('rest_api_id'),
                        stageName=self.module.params.get('name')
                    )
        except BotoCoreError as e:
            self.module.fail_json(
                msg="Error while updating stage via boto3: {}".format(e))

        return (changed, result)

    def process_request(self):
        """
        Process the user's request -- the primary code path
        :return: Returns either fail_json or exit_json
        """
        changed = False
        result = None

        self.stage = self._find_stage()

        if self.stage is not None and self.module.params.get('state', 'present') == 'absent':
            changed = self._delete_stage()
        elif self.module.params.get('state', 'present') == 'present':
            changed, result = self._update_stage()

        self.module.exit_json(changed=changed, stage=result)


def main():
    """
    Instantiates the module and calls process_request.
    :return: none
    """
    module = AnsibleModule(
        argument_spec=ApiGwStage._define_module_argument_spec(),
        supports_check_mode=True
    )

    stage = ApiGwStage(module)
    stage.process_request()


if __name__ == '__main__':
    main()
