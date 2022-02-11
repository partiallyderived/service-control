from typing import Final

from enough import JSONType
from pymongo import MongoClient
from servicecontrol.core import Service


class MongoDBService(Service):
    """Service for connecting to a MongoDB database."""

    EXPORTS: Final[frozenset[str]] = frozenset({'mongo'})
    NAME: Final[str] = 'mongo-db'
    SCHEMA: Final[JSONType] = {
        'description': 'MongoDB service configuration',
        'type': 'object',
        'properties': {
            'url': {
                'description': 'The URL of the Mongo Database.',
                'type': 'string'
            }
        },
        'required': ['url'],
        'additionalProperties': False
    }

    #: Exported MongoDB client.
    mongo: MongoClient

    def __init__(self, config: JSONType) -> None:
        """Initializes this service with the given config.

        :param config: Config to initialize with.
        """
        super().__init__(config)
        self.mongo = MongoClient(config['url'], connect=False)  # Wait to connect until actually used.

    def start(self) -> None:
        """Connects to the database."""
        self.mongo._get_topology()

    def stop(self) -> None:
        """Stops this service by closing the MongoDB client."""
        self.mongo.close()
