import logging
from collections.abc import Iterable
from logging import Formatter

from enough import FnLoggingHandler, SplitLevelLogger
from slack_sdk import WebClient


# Level, conversation ID, format string.
LoggerConfig = tuple[int, str, str]


def convo_handler(slack: WebClient, convo_id: str, level: int) -> FnLoggingHandler:
    """Creates a logger that logs messages to the given Slack channel.

    :param slack: Slack client to use to log messages.
    :param convo_id: ID of conversation to send messages to.
    :param level: Logging level to use.
    """
    return FnLoggingHandler(lambda msg: slack.chat_postMessage(channel=convo_id, text=msg), level)


def slack_logger(slack: WebClient, name: str, configs: Iterable[LoggerConfig]) -> SplitLevelLogger:
    """Given a mapping from logging levels to Slack conversation IDs, construct a SplitLevelLogger that splits messages
    between those channels depending on the log level.

    :param slack: Slack client to use.
    :param name: Name to use for this logger.
    :param configs: (level, conversation ID, % format string) for each logger.
    :return: Resulting :code:`SplitLevelLogger` instance.
    """
    level_to_logger = {}
    for level, convo_id, fmt in configs:
        formatter = Formatter(fmt)
        handler = convo_handler(slack, convo_id, level)
        handler.setFormatter(formatter)
        logger = logging.getLogger(f'{name}-{logging.getLevelName(level)}')
        logger.addHandler(handler)
        level_to_logger[level] = logger
    return SplitLevelLogger(name, level_to_logger)
