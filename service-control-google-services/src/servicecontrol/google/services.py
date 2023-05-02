from typing import Final

import googleapiclient.discovery
from enough import JSONType
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import Resource

from servicecontrol.core import Service
from servicecontrol.tools.data import DataDict


class GoogleCredsService(Service):
    """Service which provides credentials for various Google REST services."""

    EXPORTS: Final[frozenset[str]] = frozenset({'google_creds'})
    NAME: Final[str] = 'google-creds'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for GoogleCredsService.',
        'type': 'object',
        'properties': {
            'scopes': {
                'description':
                    'List of Google scopes to make credentials from.',
                'type': 'array',
                'items': {
                    'type': 'str'
                }
            },
            'user-info': {
                'description':
                    'Authorized user info to make google credentials from.',
                'type': 'object'
            }
        },
        'additionalProperties': False,
        'required': ['scopes']
    }

    # The DataDict to use to store refreshed credentials.
    _data: DataDict

    # The scopes for the credentials to have access to.
    _scopes: list[str]

    # The user info to create the credentials with.
    _user_info: JSONType

    #: The exported credentials.
    google_creds: Credentials | None

    def __init__(self, config: JSONType, data: DataDict) -> None:
        """Initializes this service from the given config.

        :param config: Config to initialize with.
        :param data: Object to use to store persistent data.
        """
        super().__init__(config)
        self._data = data
        self._scopes = config['scopes']
        self._user_info = config.get('user-info')
        self.google_creds = None

    def install(self) -> None:
        """Installs this service.

        :raise ValueError: If the key 'user-info' was not specified in the
            config.
        """
        if not self._user_info:
            raise ValueError('user-info must be specified for installation.')
        self._data[self.name]['user-info'] = self._user_info
        self._data.save()

    def installed(self) -> bool:
        """Determines whether this service is installed.

        :return: ``True`` if this is installed, ``False`` otherwise.
        """
        return self.name in self._data

    def purge(self) -> None:
        """Purge this service's persistent data."""
        self._data.pop(self.name, None)

    def start(self) -> None:
        """Starts this service by creating the credentials."""
        user_info = self._data[self.name]['user-info']
        self.google_creds = Credentials.from_authorized_user_info(
            self._scopes, user_info
        )
        self.google_creds.refresh(Request())
        self._data[self.name]['user-info'] = self.google_creds.to_json()
        self._data.save()


class GoogleSheetsService(Service):
    """Service for Google Sheets API."""

    #: Default version of the sheets API to use.
    DEFAULT_VERSION: Final[str] = 'v4'
    EXPORTS: Final[frozenset[str]] = frozenset({'google_sheets'})
    NAME: Final[str] = 'google-sheets'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for GoogleSheetsService',
        'type': 'object',
        'properties': {
            'version': {
                'description': 'API version to use ("v4" by default)',
                'type': 'string'
            }
        },
        'additionalProperties': False
    }

    # Credentials to use.
    _creds: Credentials

    #: Google Sheets API object.
    google_sheets: Resource | None

    def __init__(self, config: JSONType, google_creds: Credentials) -> None:
        """Initializes a GoogleSheetsService from the given config and Google
        credentials.

        :param config: Config to initialize with.
        :param google_creds: Google credentials to use.
        """
        super().__init__(config)
        self._creds = google_creds
        self._version = config.get('version', self.DEFAULT_VERSION)
        self.google_sheets = None

    def start(self) -> None:
        """Starts this service by creating the Google Sheets API object."""
        self.google_sheets = googleapiclient.discovery.build(
            'sheets', self._version, credentials=self._creds
        ).spreadsheets()
