from typing import Final

from enough import JSONType
from slack_bolt import App
from slack_sdk import WebClient

from servicecontrol.core import Service


class SlackBoltService(Service):
    """Provides a Slack Bolt application object and the corresponding Slack client."""

    EXPORTS: Final[frozenset[str]] = frozenset({'slack', 'slack_bolt'})
    NAME: Final[str] = 'slack-bolt'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for SlackBoltService',
        'type': 'object',
        'properties': {
            'secret': {
                'description': 'Signing secret to use.',
                'type': 'string'
            },
            'token': {
                'description': 'API token to use.',
                'type': 'string'
            }
        },
        'required': ['secret', 'token'],
        'additionalProperties': False
    }

    #: The exported Slack client.
    slack: WebClient

    #: The exported Slack Bolt application object.
    slack_bolt: App

    def __init__(self, config: JSONType) -> None:
        """Initializes the service with the given config.
        
        :param config: Config to initialize with.
        """
        super().__init__(config)
        self.slack_bolt = App(signing_secret=config['secret'], token=config['token'])
        self.slack = self.slack_bolt.client
