from unittest.mock import Mock

from slack_sdk import WebClient

import servicecontrol.slack.logservice.log as log


def test_slack_logger() -> None:
    # Test that slack_logger creates a SplitLevelLogger that sends Slack messages to different conversations in Slack
    # depending on the log level that messages was sent with.
    mock_slack = Mock(spec=WebClient)
    mock_msg = mock_slack.chat_postMessage
    configs = [
        (10, 'C1', '%(message)s'),
        (20, 'C2', '-- %(message)s --'),
        (30, 'C3', '__%(message)s__')
    ]
    logger = log.slack_logger(mock_slack, 'name', configs)
    logger.setLevel(20)
    logger.log(15, 'Hi')
    mock_msg.assert_not_called()
    logger.log(25, 'Hello')
    mock_msg.assert_called_once_with(channel='C2', text='-- Hello --')
    mock_msg.reset_mock()
    logger.setLevel(5)
    logger.log(15, 'Yo')
    mock_msg.assert_called_once_with(channel='C1', text='Yo')
    mock_msg.reset_mock()
    logger.log(35, 'init')
    mock_msg.assert_called_once_with(channel='C3', text='__init__')
