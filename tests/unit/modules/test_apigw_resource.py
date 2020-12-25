import unittest
from importlib import reload

import mock
from botocore.exceptions import BotoCoreError
from mock import patch
from plugins.modules import apigw_resource
from plugins.modules.apigw_resource import ApiGwResource


class TestApiGwResource(unittest.TestCase):

    def setUp(self):
        self.module = mock.MagicMock()
        self.module.check_mode = False
        self.module.exit_json = mock.MagicMock()
        self.module.fail_json = mock.MagicMock()
        self.resource = ApiGwResource(self.module)
        self.resource.client = mock.MagicMock()
        reload(apigw_resource)

    def test_boto_module_not_found(self):
        # Setup Mock Import Function
        import builtins as builtins
        real_import = builtins.__import__

        def mock_import(name, *args):
            if name == 'boto':
                raise ImportError
            return real_import(name, *args)

        with mock.patch('builtins.__import__', side_effect=mock_import):
            reload(apigw_resource)
            ApiGwResource(self.module)

        self.module.fail_json.assert_called_with(
            msg='boto and boto3 are required for this module')

    def test_boto3_module_not_found(self):
        # Setup Mock Import Function
        import builtins as builtins
        real_import = builtins.__import__

        def mock_import(name, *args):
            if name == 'boto3':
                raise ImportError
            return real_import(name, *args)

        with mock.patch('builtins.__import__', side_effect=mock_import):
            reload(apigw_resource)
            ApiGwResource(self.module)

        self.module.fail_json.assert_called_with(
            msg='boto and boto3 are required for this module')

    @patch.object(apigw_resource, 'boto3')
    def test_boto3_client_properly_instantiated(self, mock_boto):
        ApiGwResource(self.module)
        mock_boto.client.assert_called_once_with('apigateway')

    def test_process_request_builds_resources_dictionary(self):
        response = {
            'items': [{
                'id': 'root',
                'path': '/'
            }, {
                'id': 'abc123',
                'parentId': 'root',
                'path': '/base',
                'pathPart': 'base'
            }, {
                'id': 'def456',
                'parentId': 'abc123',
                'path': '/base/{param}',
                'pathPart': '{param}'
            }]
        }
        self.resource.client.get_resources = mock.MagicMock(
            return_value=response)

        expected = {
            'paths': {
                '/': {'id': 'root'},
                '/base': {'id': 'abc123', 'parentId': 'root'},
                '/base/{param}': {'id': 'def456', 'parentId': 'abc123'},
            }
        }

        self.resource.module.params = {
            'name': '/base/{param}', 'rest_api_id': 'rest_id'}

        self.resource.process_request()
        self.resource.client.get_resources.assert_called_once_with(
            restApiId='rest_id', limit=500)
        self.assertEqual(self.resource.path_map, expected)

    @patch.object(ApiGwResource, '_create_resource', return_value=(None, None))
    def test_process_request_calls_fail_json_when_get_resources_fails(self, mock_create):
        self.resource.client.get_resources = mock.MagicMock(
            side_effect=BotoCoreError())
        self.resource.process_request()

        self.resource.module.fail_json.assert_called_once_with(
            msg="Error calling boto3 get_resources: An unspecified error occurred")

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_request_creates_resource_when_resource_is_completely_new(self, mock_build_dict):
        mock_response = {'id': 'hurray'}
        self.resource.path_map = {'paths': {'/': {'id': 'root'}}}
        self.resource.client.create_resource = mock.MagicMock(
            return_value=mock_response)

        self.resource.module.params = {
            'name': '/resource1', 'rest_api_id': 'mock'}
        self.resource.process_request()

        self.resource.client.create_resource.assert_called_once_with(
            restApiId='mock', parentId='root', pathPart='resource1')
        self.resource.module.exit_json.assert_called_once_with(
            changed=True, resource=mock_response)

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_request_creates_missing_resources_when_resource_partially_exists(self, mock_build_dict):
        self.resource.path_map = {
            'paths': {'/': {'id': 'root'}, '/res1': {'id': 'abc', 'parentId': 'root'}}}

        responses = [{'id': 'param_id', 'path': '/res1/{param}'},
                     {'id': 'res2_id', 'path': '/res1/{param}/res2'}]
        self.resource.client.create_resource = mock.MagicMock(
            side_effect=responses)

        self.resource.module.params = {
            'name': '/res1/{param}/res2', 'rest_api_id': 'mock'}
        self.resource.process_request()

        self.assertEqual(2, self.resource.client.create_resource.call_count)
        self.resource.client.create_resource.assert_any_call(
            restApiId='mock', parentId='abc', pathPart='{param}')
        self.resource.client.create_resource.assert_called_with(
            restApiId='mock', parentId='param_id', pathPart='res2')

        # Ensure only final resource is returned
        self.resource.module.exit_json.assert_called_once_with(
            changed=True, resource=responses[1])

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_request_calls_fail_json_when_create_resource_fails(self, mock_build_dict):
        self.resource.path_map = {'paths': {'/': {'id': 'root'}}}
        self.resource.client.create_resource = mock.MagicMock(
            side_effect=BotoCoreError())

        self.resource.module.params = {
            'name': '/resource1', 'rest_api_id': 'mock'}
        self.resource.process_request()

        self.resource.client.create_resource.assert_called_once_with(
            restApiId='mock', parentId='root', pathPart='resource1')
        self.resource.module.fail_json.assert_called_once_with(
            msg='Error calling boto3 create_resource: An unspecified error occurred')

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_skips_create_and_returns_existing_data_when_resource_exists(self, mock_build_dict):
        self.resource.path_map = {'paths': {
            '/': {'id': 'root'}, '/resource1': {'id': 'abc', 'parentId': 'root'}}}
        self.resource.client.create_resource = mock.MagicMock()

        expected = {'id': 'abc', 'parentId': 'root', 'path': '/resource1'}

        self.resource.module.params = {
            'name': '/resource1', 'rest_api_id': 'mock'}
        self.resource.process_request()

        self.assertEqual(0, self.resource.client.create_resource.call_count)
        self.resource.module.exit_json.assert_called_once_with(
            changed=False, resource=expected)

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_skips_create_when_check_mode_enabled(self, mock_build_dict):
        self.resource.path_map = {'paths': {'/': {'id': 'root'}}}
        self.resource.client.create_resource = mock.MagicMock()

        self.resource.module.check_mode = True

        self.resource.module.params = {
            'name': '/resource1', 'rest_api_id': 'mock'}
        self.resource.process_request()

        self.assertEqual(0, self.resource.client.create_resource.call_count)
        self.resource.module.exit_json.assert_called_once_with(
            changed=True, resource=None)

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_request_deletes_resource_when_resource_is_present(self, mock_build_dict):
        self.resource.path_map = {'paths': {
            '/': {'id': 'root'}, '/resource1': {'id': 'abc', 'parentId': 'root'}}}
        self.resource.client.delete_resource = mock.MagicMock()

        self.resource.module.params = {
            'name': '/resource1', 'rest_api_id': 'mock', 'state': 'absent'}
        self.resource.process_request()

        self.resource.client.delete_resource.assert_called_once_with(
            restApiId='mock', resourceId='abc')
        self.resource.module.exit_json.assert_called_once_with(
            changed=True, resource=None)

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_request_calls_fail_json_when_delete_resource_fails(self, mock_build_dict):
        self.resource.path_map = {'paths': {
            '/': {'id': 'root'}, '/resource1': {'id': 'abc', 'parentId': 'root'}}}
        self.resource.client.delete_resource = mock.MagicMock(
            side_effect=BotoCoreError())

        self.resource.module.params = {
            'name': '/resource1', 'rest_api_id': 'mock', 'state': 'absent'}
        self.resource.process_request()

        self.resource.client.delete_resource.assert_called_once_with(
            restApiId='mock', resourceId='abc')
        self.resource.module.fail_json.assert_called_once_with(
            msg='Error calling boto3 delete_resource: An unspecified error occurred')

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_request_skips_delete_when_resource_is_missing(self, mock_build_dict):
        self.resource.path_map = {'paths': {'/': {'id': 'root'}}}
        self.resource.client.delete_resource = mock.MagicMock()

        self.resource.module.params = {
            'name': '/resource1', 'rest_api_id': 'mock', 'state': 'absent'}
        self.resource.process_request()

        self.assertEqual(0, self.resource.client.delete_resource.call_count)
        self.resource.module.exit_json.assert_called_once_with(
            changed=False, resource=None)

    @patch.object(ApiGwResource, '_build_resource_dictionary')
    def test_process_request_skips_delete_when_check_mode_enabled(self, mock_build_dict):
        self.resource.path_map = {
            'paths': {'/': {'id': 'root'}, '/del': {'id': 'abc'}}}
        self.resource.client.delete_resource = mock.MagicMock()

        self.resource.module.check_mode = True
        self.resource.module.params = {
            'name': '/del', 'rest_api_id': 'mock', 'state': 'absent'}
        self.resource.process_request()

        self.assertEqual(0, self.resource.client.delete_resource.call_count)
        self.resource.module.exit_json.assert_called_once_with(
            changed=True, resource=None)

    def test_define_argument_spec(self):
        result = ApiGwResource._define_module_argument_spec()
        self.assertIsInstance(result, dict)
        self.assertEqual(result, dict(
                         name=dict(required=True),
                         rest_api_id=dict(required=True),
                         state=dict(default='present', choices=[
                                    'present', 'absent'])
                         ))

    @patch.object(apigw_resource, 'AnsibleModule')
    @patch.object(apigw_resource, 'ApiGwResource')
    def test_main(self, mock_ApiGwResource, mock_AnsibleModule):
        mock_ApiGwResource_instance = mock.MagicMock()
        mock_AnsibleModule_instance = mock.MagicMock()
        mock_ApiGwResource.return_value = mock_ApiGwResource_instance
        mock_AnsibleModule.return_value = mock_AnsibleModule_instance

        apigw_resource.main()

        mock_ApiGwResource.assert_called_once_with(mock_AnsibleModule_instance)
        self.assertEqual(
            1, mock_ApiGwResource_instance.process_request.call_count)


if __name__ == '__main__':
    unittest.main()
