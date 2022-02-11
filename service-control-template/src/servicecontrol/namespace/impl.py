from typing import Final

from enough import JSONType

from servicecontrol.core import Service


class TheService(Service):
    """Service description."""

    EXPORTS: Final[frozenset[str]] = ...
    NAME: Final[str] = ...
    SCHEMA: Final[JSONType] = {
        'description': 'Config for ...',
        'type': 'object',
        ...: ...
    }

    def __init__(self, config: JSONType) -> None:
        """Initializes the service with the given config.
        
        :param config: Config to initialize with.
        """
        super().__init__(config)
        ...
