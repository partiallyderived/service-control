from __future__ import annotations

import json
import os.path
from collections import UserDict
from threading import Lock
from typing import Final

from enough import JSONType

from servicecontrol.core import Service


class DataDict(UserDict):
    """Thin wrapper around :code:`dict` which provides :meth:`.DataDict.save`, a method which saves its state to disk.
    """
    def __init__(self, parent: DataService, *args: object, **kwargs: object) -> None:
        """Initializes this with the given parent service and any arguments to pass to :code:`dict`.

        :param parent: Parent service.
        :param args: Positional arguments to pass to :code:`dict`.
        :param kwargs: Keyword arguments to pass to :code:`dict`.
        """
        super().__init__(*args, **kwargs)
        self._parent = parent

    def save(self) -> None:
        """Saves this dictionary to disk."""
        self._parent.save()


class DataService(Service):
    """Maintains dynamic data for other services which are persistent across launches."""

    EXPORTS: Final[frozenset[str]] = frozenset({'data'})
    NAME: Final[str] = 'data'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for DataService.',
        'properties': {
            'path': {
                'description': 'Path to JSON file to save data to.',
                'type': 'string'
            }
        },
        'required': ['path'],
        'additionalProperties': False
    }

    # Lock to prevent concurrent saves.
    _lock: Lock

    #: The modifiable data exported by this service.
    data: DataDict

    #: The path where the JSON containing the data is saved.
    path: str

    def __init__(self, config: JSONType) -> None:
        """Initializes the service with the given config.

        :param config: Config to initialize with.
        """
        super().__init__(config)
        self._lock = Lock()
        self.data = DataDict(self)
        self.path = config['path']

    def purge(self) -> None:
        """Removes the JSON file for which the data is stored."""
        if os.path.isfile(self.path):
            os.remove(self.path)

    def save(self) -> None:
        """Saves the state of the data."""
        with self._lock:
            with open(self.path, 'w') as f:
                json.dump(self.data.data, f)

    def start(self) -> None:
        """Starts this service by loading the existing JSON data, if it exists."""
        if os.path.isfile(self.path):
            with open(self.path) as f:
                self.data = DataDict(self, json.load(f))

    def stop(self) -> None:
        """Stops this service, saving its data beforehand."""
        self.save()
