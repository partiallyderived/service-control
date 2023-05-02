from unittest.mock import Mock

from google.oauth2.credentials import Credentials

from servicecontrol.google.services import (
    GoogleCredsService, GoogleSheetsService
)
from servicecontrol.tools.data import DataDict


def test_creds() -> None:
    # Just verify that GoogleCredsService can be initialized without errors.
    config = {'scopes': ['scope1', 'scope2'], 'user-info': {'info': 'data'}}
    mock_data = Mock(spec=DataDict)
    service = GoogleCredsService(config, mock_data)
    assert service._data == mock_data
    assert service._scopes == config['scopes']
    assert service._user_info == config['user-info']
    assert service.google_creds is None


def test_sheets() -> None:
    # Just verify that GoogleSheetsService can be initialized without errors.
    config = {'version': 'v3'}
    mock_creds = Mock(spec=Credentials)
    service = GoogleSheetsService(config, mock_creds)
    assert service._creds == mock_creds
    assert service._version == 'v3'
    assert service.google_sheets is None
