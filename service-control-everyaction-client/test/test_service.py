import unittest.mock as mock

from servicecontrol.everyaction.client import EAClientService


def test_service() -> None:
    # Just test that EAClientService instantiates an EAClient with the
    # appropriate arguments.
    config = {'app': 'AppName', 'key': 'MyKey'}
    with mock.patch(
        'servicecontrol.everyaction.client.EAClient', autospec=True
    ) as mock_client_class:
        service = EAClientService(config)
        assert service.ea == mock_client_class.return_value
        mock_client_class.assert_called_with(config['app'], config['key'])
