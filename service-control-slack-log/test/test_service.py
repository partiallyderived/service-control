import logging
import unittest.mock as mock
from unittest.mock import Mock

import pytest
from slack_sdk import WebClient

from servicecontrol.slack.logservice import SlackLogService


def test_service() -> None:
    # Test that SlackLogService initializes correctly.
    config = {
        'default-format': '-- %(message)s --',
        'level': 'DEBUG',
        'level-configs': [{
            'convo': 'C1',
            'level': 'InFo'
        }, {
            'convo': 'C2',
            'level': 35,
            'format': '%(message)s'
        }, {
            'convo': 'C3',
            'level': 'error',
            'format': '__%(message)s__'
        }],
        'name': 'test-name'
    }
    mock_slack = Mock(spec=WebClient)
    with mock.patch(
        'servicecontrol.slack.logservice.log.slack_logger', autospec=True
    ) as mock_slack_logger:
        service = SlackLogService(config, mock_slack)
        mock_slack_logger.assert_called_with(mock_slack, 'test-name', [
            (logging.getLevelName('INFO'), 'C1', '-- %(message)s --'),
            (35, 'C2', '%(message)s'),
            (logging.getLevelName('ERROR'), 'C3', '__%(message)s__')
        ])
        assert service.slack_log == mock_slack_logger.return_value
        mock_slack_logger.return_value.setLevel.assert_called_with(
            logging.getLevelName('DEBUG')
        )
        with pytest.raises(
            ValueError, match='Unrecognized logging level name "INF"'
        ):
            # Test that unrecognized level name 'INF' results in an error.
            config['level-configs'][0]['level'] = 'INF'
            SlackLogService(config, mock_slack)
