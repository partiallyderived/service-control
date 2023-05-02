from typing import Final

from enough import JSONType
from everyaction import EAClient
from servicecontrol.core import Service


class EAClientService(Service):
    """Service which provides an EveryAction client object."""

    EXPORTS: Final[frozenset[str]] = frozenset({'ea'})
    NAME: Final[str] = 'everyaction-client'
    SCHEMA: Final[JSONType] = {
        'description': 'EveryAction client service configuration.',
        'type': 'object',
        'properties': {
            'app': {
                'description': 'The EveryAction application name.',
                'type': 'string'
            },
            'key': {
                'description': (
                    'The EveryAction API key. Must end with |0 or |1 to '
                    'indicate VoterFile or MyCampaign mode respectively.',
                ),
                'type': 'string'
            }
        },
        'required': ['app', 'key'],
        'additionalProperties': False
    }

    #: The exported client.
    ea: EAClient

    def __init__(self, config: JSONType) -> None:
        """Initializes the service with the given config.

        :param config: Config to initialize with.
        """
        super().__init__(config)
        app = config['app']
        key = config['key']
        self.ea = EAClient(app, key)

    def stop(self) -> None:
        """Stops this service by stopping the exported EveryAction client."""
        self.ea.close()
