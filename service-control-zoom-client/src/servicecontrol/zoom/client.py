from __future__ import annotations

import time
from typing import Final

from enough import JSONType
from requests import Response, Session

from servicecontrol.core import Service
from servicecontrol.tools.data import DataDict


class ZoomClientService(Service):
    """Zoom API client service."""
    #: Base URL for zoom requests.
    BASE: Final[str] = 'https://api.zoom.us/v2/'

    #: URL to use to refresh token.
    TOKEN_URL: Final[str] = 'https://zoom.us/oauth/token'

    EXPORTS: Final[frozenset[str]] = frozenset({'zoom'})
    NAME: Final[str] = 'zoom-client'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for ZoomClientService.',
        'type': 'object',
        'properties': {
            'id': {
                'description': 'Zoom ID to use.',
                'type': 'string'
            },
            'refresh': {
                'description': 'Zoom refresh token to use on installation.',
                'type': 'string'
            },
            'secret': {
                'description': 'Zoom secret to use.',
                'type': 'string'
            }
        },
        'required': ['id', 'secret'],
        'additionalProperties': False
    }

    # Authentication tuple (id, secret) to use for the session.
    _auth: tuple[str, str]

    # Mapping to store persistent data in.
    _data: DataDict

    # A minute before the refresh token is set to expire.
    _expire_time: float | None

    # The refresh token being used.
    _refresh_token: str | None

    # The requests session being used.
    _session: Session

    # The token being used.
    _token: str | None

    #: Zoom client to export.
    zoom: ZoomClientService

    def __init__(self, config: JSONType, data: DataDict) -> None:
        """Initializes this service with the given config and dependencies.

        :param config: Config to initialize with.
        :param data: Mapping to store persistent data in.
        """
        super().__init__(config)
        self.zoom = self

        self._auth = (config['id'], config['secret'])
        self._data = data
        self._expire_time = None
        self._refresh_token = config.get('refresh')
        self._session = Session()
        self._token = None

    def _refresh(self) -> None:
        # Use this service's refresh token to refresh credentials.
        resp = self._session.post(
            self.TOKEN_URL,
            auth=self._auth,
            params={'grant_type': 'refresh_token', 'refresh_token': self._refresh_token},
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        resp.raise_for_status()
        # Set expiration time one minute beforehand to avoid a situation where the token has not expired when we check
        # the expiration time but has expired before the serve received the request.
        self._expire_time = time.time() + resp.json()['expires_in'] - 60
        self._token = resp.json()['access_token']
        self._refresh_token = resp.json()['refresh_token']
        self._data[self.name]['refresh'] = self._refresh_token
        self._data.save()

    def _send(self, verb: str, path: str, **kwargs: object) -> Response:
        # Sends a request to the Zoom API URL.
        if time.time() >= self._expire_time:
            self._refresh()
        method = getattr(self._session, verb)
        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {self._token}'
        resp = method(f'{self.BASE}/{path}', headers=headers, **kwargs)
        resp.raise_for_status()
        return resp

    def install(self) -> None:
        """Installs this service.

        :raise ValueError: If "refresh" was not specified in the config for this service.
        """
        if not self._refresh_token:
            raise ValueError('"refresh" must be specified for installation.')
        self._data[self.name] = {'refresh': self._refresh_token}
        self._data.save()

    def installed(self) -> bool:
        """Determines whether this service is installed.

        :return: :code:`True` if this service is installed, :code:`False` otherwise.
        """
        return self.name in self._data

    def purge(self) -> None:
        """Purges persistent data for this service."""
        del self._data[self.name]
        self._data.save()

    def start(self) -> None:
        """Starts this service so that it is ready to send requests."""
        self._refresh_token = self._data[self.name]['refresh']
        self._refresh()

    def stop(self) -> None:
        """Stops this service. Afterwards, it will no longer be able to send requests."""
        self._session.close()

    def delete(self, path: str, **kwargs: object) -> Response:
        """Sends a DELETE request.

        :param path: Path to send request to.
        :param kwargs: JSON arguments for the request.
        :return: The resulting response.
        """
        return self._send('delete', path, **kwargs)

    def get(self, path: str, **kwargs: object) -> Response:
        """Sends a GET request.

        :param path: Path to send request to.
        :param kwargs: JSON arguments for the request.
        :return: The resulting response.
        """
        return self._send('get', path, **kwargs)

    def patch(self, path: str, **kwargs: object) -> Response:
        """Sends a PATCH request.

        :param path: Path to send request to.
        :param kwargs: JSON arguments for the request.
        :return: The resulting response.
        """
        return self._send('patch', path, **kwargs)

    def post(self, path: str, **kwargs: object) -> Response:
        """Sends a POST request.

        :param path: Path to send request to.
        :param kwargs: JSON arguments for the request.
        :return: The resulting response.
        """
        return self._send('post', path, **kwargs)

    def put(self, path: str, **kwargs: object) -> Response:
        """Sends a PUT request.

        :param path: Path to send request to.
        :param kwargs: JSON arguments for the request.
        :return: The resulting response.
        """
        return self._send('put', path, **kwargs)
