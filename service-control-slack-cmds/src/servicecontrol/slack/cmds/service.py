from logging import Logger, LoggerAdapter
from typing import Final

import enough as br
from enough import JSONType
from keywordcommands import CommandGroup
from slack_bolt import App

from servicecontrol.core import Service
from servicecontrol.slack.cmds.state import SlackCommandsState
from servicecontrol.slack.cmds.handler import SlackCommandsHandler


class SlackCommandsService(Service):
    """Service which can load keyword commands from modules for use in Slack."""
    # Handler to use for the service.
    _handler: SlackCommandsHandler

    # The state to use for the service.
    _state: SlackCommandsState

    EXPORTS: Final[frozenset[str]] = frozenset()
    NAME: Final[str] = 'slack-cmds'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for SlackCommandsService.',
        'type': 'object',
        'properties': {
            'root': {
                'description': 'Fully-qualified name of the :class:`.CommandGroup` to use as the root for commands.',
                'type': 'string'
            }
        },
        'required': ['root'],
        'additionalProperties': False
    }

    def __init__(self, config: JSONType, bolt: App, log: Logger | LoggerAdapter) -> None:
        """Initializes the service with the given config.
        
        :param config: Config to initialize with.
        :param bolt: Slack bolt application to use to register commands.
        :param log: Callable to use to log server messages.
        :raise TypeError: If :code:`not isinstance(config['root'], CommandGroup`.
        """
        super().__init__(config)
        root = br.import_object(config['root'])
        if not isinstance(root, CommandGroup):
            raise TypeError(f'Root object {root} (found at {config["root"]}) is not an instance of CommandGroup.')
        self._state = SlackCommandsState(config['name'], root, bolt=bolt, log=log)
        self._handler = SlackCommandsHandler()

    def start(self) -> None:
        """Start the service by registering the handler with the Slack bolt application."""
        self._handler.register(self._state)
