import logging
from typing import Final

from enough import JSONType, SplitLevelLogger
from slack_sdk import WebClient

import servicecontrol.slack.logservice.log
from servicecontrol.core import Service


class SlackLogService(Service):
    """Service which provides a callable that sends a message to a specified Slack channel."""
    # Names of each recognized logging level.
    _LEVEL_NAMES: Final[set[str]] = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}

    #: Default value to use for log levels that do not have a format specified.
    DEFAULT_FORMAT: Final[str] = '%(message)s'

    #: Default level to log at.
    DEFAULT_LEVEL: Final[str] = 'INFO'

    #: Default name to give to the logger.
    DEFAULT_NAME: Final[str] = 'slack'

    #: Exported logger.
    slack_log: SplitLevelLogger

    EXPORTS: Final[frozenset[str]] = frozenset({'slack_log'})
    NAME: Final[str] = 'slack-log'
    SCHEMA: JSONType = {
        'description': 'Config for Slack Log service.',
        'type': 'object',
        'properties': {
            'default-format': {
                'description': f'The format string to use to format messages by default ({DEFAULT_FORMAT} by default).',
                'type': 'string'
            },
            'level': {
                'description': f'Level to set logger to ({DEFAULT_LEVEL} by default).',
                'type': ['number', 'string']
            },
            'level-configs': {
                'description': 'Configs objects for each level.',
                'type': 'array',
                'items': {
                    'description': 'Config for a log level.',
                    'type': 'object',
                    'properties': {
                        'convo': {
                            'description': 'ID of the channel to log to.',
                            'type': 'string'
                        },
                        'format': {
                            'description': 'Format string to use for this logging level.',
                            'type': 'string'
                        },
                        'level': {
                            'description': 'The logging level this config is for. May be a number or a string.',
                            'type': ['number', 'string']
                        }
                    },
                    'additionalProperties': False,
                    'minItems': 1,
                    'required': ['convo', 'level']
                }
            },
            'name': {
                'description': f'Name to to give to the logger ({DEFAULT_NAME} by default).'
            }
        },
        'required': ['level-configs'],
        'additionalProperties': False
    }

    @staticmethod
    def _ensure_level(name_or_level: int | str) -> int:
        # Ensure that the given level is an integer level.
        if isinstance(name_or_level, str):
            upper = name_or_level.upper()
            if upper not in SlackLogService._LEVEL_NAMES:
                raise ValueError(f'Unrecognized logging level name "{name_or_level}".')
            return logging.getLevelName(upper)
        return name_or_level

    def __init__(self, config: JSONType, slack: WebClient) -> None:
        """Initializes the service with the given config.

        :param config: Config to initialize with.
        :param slack: Slack client to initialize with.
        :raise ValueError: If a string given for a logging level is not, case-insensitively, DEBUG, INFO, WARNING,
            ERROR, or CRITICAL.
        """
        super().__init__(config)
        default_format = config.get('default-format', self.DEFAULT_FORMAT)
        name = config.get('name', self.DEFAULT_NAME)
        logger_configs = []
        for conf in config['level-configs']:
            convo = conf['convo']
            level = self._ensure_level(conf['level'])
            fmt = conf.get('format', default_format)
            logger_configs.append((level, convo, fmt))
        self.slack_log = servicecontrol.slack.logservice.log.slack_logger(slack, name, logger_configs)
        level = self._ensure_level(config.get('level', self.DEFAULT_LEVEL))
        self.slack_log.setLevel(level)
