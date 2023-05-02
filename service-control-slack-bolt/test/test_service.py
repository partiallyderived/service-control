import unittest.mock as mock

from servicecontrol.slack.bolt import SlackBoltService


def test_service() -> None:
    # Just test that SlackBoltService initializes correctly.
    config = {'secret': 'my-secret', 'token': 'my-token'}
    with mock.patch('servicecontrol.slack.bolt.App') as mock_app_class:
        service = SlackBoltService(config)
        assert service.slack_bolt == mock_app_class.return_value
        assert service.slack == service.slack_bolt.client
        mock_app_class.assert_called_with(
            signing_secret=config['secret'], token=config['token']
        )
