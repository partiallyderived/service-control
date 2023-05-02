import unittest.mock as mock

from servicecontrol.mongodb.db import MongoDBService


def test_service() -> None:
    # Just test that the service instantiates the MongoClient correctly.
    config = {'url': 'file:///who/cares'}
    with mock.patch(
        'servicecontrol.mongodb.db.MongoClient'
    ) as mock_client_class:
        service = MongoDBService(config)
        assert service.mongo == mock_client_class.return_value
        mock_client_class.assert_called_with(config['url'], connect=False)
