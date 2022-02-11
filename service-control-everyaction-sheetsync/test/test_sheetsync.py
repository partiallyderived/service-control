import sched
import unittest.mock as mock
from unittest.mock import Mock

import pytest
from enough import JSONType
from everyaction.objects import ActivistCode

from servicecontrol.everyaction.cache import IDNameListCache
from servicecontrol.everyaction.contacts import EAContactsService
from servicecontrol.everyaction.sheetsync import EASheetSyncService


@pytest.fixture
def alice() -> JSONType:
    # A contact to test with named Alice.
    return {
        'first': 'Alice',
        'last': 'Allison',
        'emails': ['alice@alice.com'],
        'phones': ['1234567890'],
        'do_not_email': True,
        'do_not_call': False,
        'codes': [1, 2]
    }


@pytest.fixture
def bob() -> JSONType:
    # A contact to test with named Bob.
    return {
        'first': 'Bob',
        'emails': [],
        'phones': ['0123456789', '1111111111'],
        'do_not_call': True,
        'codes': [1]
    }


@pytest.fixture
def activist_code_cache() -> IDNameListCache[ActivistCode]:
    # Activist code cache to use for testing.
    # noinspection PyTypeChecker
    return IDNameListCache(lambda: [
        ActivistCode(name='Code1', id=1),
        ActivistCode(name='Code2', id=2),
        ActivistCode(name='Code3', id=3)
    ])


@pytest.fixture
def code_to_sheet() -> dict[str, str]:
    # Value of config['code-to-sheet'] to use for testing.
    return {
        'Code1': 'Sheet1',
        'Code2': 'Sheet2',
        'Code3': 'Sheet3'
    }


@pytest.fixture
def config(code_to_sheet: dict[str, str]) -> JSONType:
    # Config to use for testing.
    return {
        'code-to-sheet': code_to_sheet,
        'period': 1800
    }


@pytest.fixture
def mock_contacts() -> Mock:
    # Mock EAContactsService to use for testing.
    return Mock(spec=EAContactsService)


@pytest.fixture
def mock_sheets() -> Mock:
    # Mock Google Sheets Resource object ot use for testing.
    return Mock()


@pytest.fixture
def scheduler() -> sched.scheduler:
    # The scheduler to use for testing.
    return sched.scheduler()


@pytest.fixture
def service(
    config: JSONType,
    activist_code_cache: IDNameListCache[ActivistCode],
    mock_contacts: Mock,
    mock_sheets: Mock,
    scheduler: sched.scheduler
) -> EASheetSyncService:
    # Service instance to use for testing.
    # noinspection PyTypeChecker
    return EASheetSyncService(
        config,
        activist_code_cache=activist_code_cache,
        ea_contacts=mock_contacts,
        google_sheets=mock_sheets,
        scheduler=scheduler
    )


def test_sheet_helper_fns() -> None:
    # Test that EASheetSyncService._sheet_str_row correctly converts several values into a JSON representing the row
    # content for Google Sheets.
    row = EASheetSyncService._sheet_str_row('First', 'Last', 'Email', 'Phone')
    assert row == {
        'values': [
            {'userEnteredValue': {'stringValue': 'First'}},
            {'userEnteredValue': {'stringValue': 'Last'}},
            {'userEnteredValue': {'stringValue': 'Email'}},
            {'userEnteredValue': {'stringValue': 'Phone'}}
        ]
    }

    # Test that EASheetSyncService._add_suppression_color adds a Cell background color corresponding to
    # EASheetSyncService._SUPPRESSION_COLOR.
    EASheetSyncService._add_suppression_color(row['values'][2])
    assert row['values'][2] == {
        'userEnteredValue': {'stringValue': 'Email'},
        'userEnteredFormat': {
            'backgroundColor': {
                'red': EASheetSyncService._SUPPRESSION_COLORS[0],
                'blue': EASheetSyncService._SUPPRESSION_COLORS[1],
                'green': EASheetSyncService._SUPPRESSION_COLORS[2]
            }
        }
    }


def test_init(
    config: JSONType,
    activist_code_cache: IDNameListCache[ActivistCode],
    mock_contacts: Mock,
    mock_sheets: Mock,
    scheduler: sched.scheduler
) -> None:
    # Test initialization of a service.
    # noinspection PyTypeChecker
    service = EASheetSyncService(
        config,
        activist_code_cache=activist_code_cache,
        ea_contacts=mock_contacts,
        google_sheets=mock_sheets,
        scheduler=scheduler
    )
    assert service._period == config['period']
    assert service._code_to_sheet == {
        1: 'Sheet1',
        2: 'Sheet2',
        3: 'Sheet3'
    }

    # Test with default period.
    del config['period']
    # noinspection PyTypeChecker
    service = EASheetSyncService(
        config,
        activist_code_cache=activist_code_cache,
        ea_contacts=mock_contacts,
        google_sheets=mock_sheets,
        scheduler=scheduler
    )
    assert service._period == EASheetSyncService.DEFAULT_PERIOD


def test_update_sheet(service: EASheetSyncService, alice: JSONType, bob: JSONType, mock_sheets: Mock) -> None:
    # Test that EASheetSyncService._update_sheet updates a sheet with new contacts.
    row1 = EASheetSyncService._sheet_str_row('First', 'Last', 'Email', 'Phone')
    row2 = EASheetSyncService._sheet_str_row('Alice', 'Allison', 'alice@alice.com', '1234567890')
    row3 = EASheetSyncService._sheet_str_row('Bob', '', '', '0123456789')
    EASheetSyncService._add_suppression_color(row2['values'][2])  # Since Alice is marked as Do Not Email.
    EASheetSyncService._add_suppression_color(row3['values'][-1])  # Since Bob is marked as Do Not Call.

    service._update_sheet('Sheet1', [alice, bob])
    mock_sheets.batchUpdate.assert_called_with(
        spreadsheetId='Sheet1',
        body={
            'requests': [{
                'updateCellsRequest': {
                    'rows': [row1, row2, row3],
                    'start': {
                        'sheetId': 0,
                        'rowIndex': 0,
                        'columnIndex': 0
                    }
                }
            }]
        }
    )


def test_update_sheets(service: EASheetSyncService, alice: JSONType, bob: JSONType, mock_contacts: Mock) -> None:
    # Test that EASheetSyncService._update_sheets updates each sheet with the contacts who have the corresponding codes.
    mock_contacts.find.return_value = [alice, bob]
    with mock.patch.object(service, '_update_sheet') as mock_update:
        service._update_sheets()
        mock_update.assert_has_calls([
            mock.call('Sheet1', [alice, bob]),  # Both have activist code with ID 1.
            mock.call('Sheet2', [alice]),  # Only Alice has activist code with ID 2.
            mock.call('Sheet3', [])  # Neither Alice nor Bob has activist code with ID 3.
        ], any_order=True)
