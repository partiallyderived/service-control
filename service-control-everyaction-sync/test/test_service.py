import sched
import unittest.mock as mock
from collections.abc import Mapping
from typing import Final
from unittest.mock import Mock

import pytest
from everyaction import EAClient
from everyaction.objects import ChangedEntityField, ChangeType
from everyaction.services import ChangedEntities

from servicecontrol.tools.data import DataDict, DataService
from servicecontrol.everyaction.contacts import ContactUpdate, EAContactsService
from servicecontrol.everyaction.sync import EAContactsSyncService


# Use these to simulate Change Types with IDs.
CREATED_ID: Final[int] = 1
CREATED_OR_UPDATED_ID: Final[int] = 2
DELETED_ID: Final[int] = 3


@pytest.fixture
def change_types_cache() -> dict[str, dict[int | str, ChangeType]]:
    # Creates a mapping to use as a stand-in for the "change_types_cache" __init__ argument.
    created_type = ChangeType(id=CREATED_ID, name='Created')
    created_or_updated_type = ChangeType(id=CREATED_OR_UPDATED_ID, name='CreatedOrUpdated')
    deleted_type = ChangeType(id=DELETED_ID, name='Deleted')
    change_types_cache = {
        'Contacts': {
            created_or_updated_type.id: created_or_updated_type,
            created_or_updated_type.name: created_or_updated_type,
            deleted_type.id: deleted_type,
            deleted_type.name: deleted_type
        },
        'ContactsActivistCodes': {
            created_type.id: created_type,
            created_type.name: created_type,
            deleted_type.id: deleted_type,
            deleted_type.name: deleted_type
        }
    }
    return change_types_cache


@pytest.fixture
def data() -> DataDict:
    # Creates a DataDict to use as a stand-in for the "data" __init__ argument.
    return DataDict(Mock(spec=DataService))


@pytest.fixture
def entity_fields_cache() -> dict[str, dict[str, ChangedEntityField]]:
    # Creates a mapping to use as a stand-in for the "entity_fields_cache" __init__ argument.
    return {
        'Contacts': {
            'ChangeTypeID': ChangedEntityField(name='ChangeTypeID', type='N'),
            'DoNotCall': ChangedEntityField(name='DoNotCall', type='B'),
            'DoNotEmail': ChangedEntityField(name='DoNotEmail', type='B'),
            'FirstName': ChangedEntityField(name='FirstName', type='T'),
            'LastName': ChangedEntityField(name='LastName', type='T'),
            'PersonalEmail': ChangedEntityField(name='PersonalEmail', type='T'),
            'Phone': ChangedEntityField(name='Phone', type='T'),
            'VanID': ChangedEntityField(name='VanID', type='N')
        },
        'ContactsActivistCodes': {
            'ActivistCodeID': ChangedEntityField(name='ActivistCodeID', type='N'),
            'ChangeTypeID': ChangedEntityField(name='ChangeTypeID', type='N'),
            'VanID': ChangedEntityField(name='VanID', type='N')
        }
    }


@pytest.fixture
def mock_ea() -> Mock:
    # Returns a mocked EveryAction client.
    result = Mock(spec=EAClient)
    result.changed_entities = Mock(spec=ChangedEntities)
    return result


@pytest.fixture
def mock_ea_contacts() -> Mock:
    # Returns a mocked EAContactsService object.
    return Mock(spec=EAContactsService)


@pytest.fixture
def scheduler() -> sched.scheduler:
    # A default scheduler to use for EAContactsSyncService.__init__.
    return sched.scheduler()


@pytest.fixture
def service(
    change_types_cache: Mapping[str, Mapping[int | str, ChangeType]],
    data: DataDict,
    entity_fields_cache: Mapping[str, Mapping[str, ChangedEntityField]],
    mock_ea: Mock,
    mock_ea_contacts: Mock,
    scheduler: sched.scheduler
) -> EAContactsSyncService:
    # Gives an instance of EAContactsSyncService to test on.
    # noinspection PyTypeChecker
    result = EAContactsSyncService(
        {},
        change_types_cache=change_types_cache,
        data=data,
        ea=mock_ea,
        ea_contacts=mock_ea_contacts,
        entity_fields_cache=entity_fields_cache,
        scheduler=scheduler
    )
    result.name = result.NAME
    return result


def test_delete_handlers() -> None:
    # Test that delete handlers update the state of a ContactUpdate so that the relevant data is deleted.
    update = ContactUpdate(1)

    # Values should be ignored for these.
    EAContactsSyncService._DELETE_HANDLERS['DoNotCall'](update, 'A')
    EAContactsSyncService._DELETE_HANDLERS['DoNotEmail'](update, 'B')
    EAContactsSyncService._DELETE_HANDLERS['FirstName'](update, 'C')
    EAContactsSyncService._DELETE_HANDLERS['LastName'](update, 'D')

    # Values matter for these.
    EAContactsSyncService._DELETE_HANDLERS['PersonalEmail'](update, 'alice@alice.com')
    EAContactsSyncService._DELETE_HANDLERS['Phone'](update, '1234567890')

    assert update.do_not_call == ''
    assert update.do_not_email == ''
    assert update.first == ''
    assert update.last == ''
    assert update.del_emails == ['alice@alice.com']
    assert update.del_phones == ['1234567890']

    assert update.add_codes is None
    assert update.add_emails is None
    assert update.add_phones is None


def test_update_handlers() -> None:
    # Test that delete handlers update the state of a ContactUpdate so that the relevant data is updated.
    update = ContactUpdate(1)

    EAContactsSyncService._UPDATE_HANDLERS['DoNotCall'](update, True)
    EAContactsSyncService._UPDATE_HANDLERS['DoNotEmail'](update, False)
    EAContactsSyncService._UPDATE_HANDLERS['FirstName'](update, 'Alice')
    EAContactsSyncService._UPDATE_HANDLERS['LastName'](update, 'Allison')
    EAContactsSyncService._UPDATE_HANDLERS['PersonalEmail'](update, 'alice@alice.com')
    EAContactsSyncService._UPDATE_HANDLERS['Phone'](update, '1234567890')

    assert update.do_not_call is True
    assert update.do_not_email is False
    assert update.first == 'Alice'
    assert update.last == 'Allison'
    assert update.add_emails == ['alice@alice.com']
    assert update.add_phones == ['1234567890']

    assert update.del_codes is None
    assert update.del_emails is None
    assert update.del_phones is None


def test_init(
    change_types_cache: Mapping[str, Mapping[int | str, ChangeType]],
    data: DataDict,
    entity_fields_cache: Mapping[str, Mapping[str, ChangedEntityField]],
    mock_ea: Mock,
    mock_ea_contacts: Mock,
    scheduler: sched.scheduler
) -> None:
    # Test that initialization of EAContactsSyncService behaves correctly.

    # Default config initialization.
    # noinspection PyTypeChecker
    service = EAContactsSyncService(
        {},
        change_types_cache=change_types_cache,
        data=data,
        ea=mock_ea,
        ea_contacts=mock_ea_contacts,
        entity_fields_cache=entity_fields_cache,
        scheduler=scheduler
    )
    assert service._period == EAContactsSyncService.DEFAULT_PERIOD
    assert service._start_time is None

    # Now populate the config.
    # noinspection PyTypeChecker
    service = EAContactsSyncService(
        {'period': 1800, 'start': '2000-03-25T03:45:00'},
        change_types_cache=change_types_cache,
        data=data,
        ea=mock_ea,
        ea_contacts=mock_ea_contacts,
        entity_fields_cache=entity_fields_cache,
        scheduler=scheduler
    )
    assert service._period == 1800
    assert service._start_time == '2000-03-25T03:45:00'

    # Try with an invalid iso date.
    with pytest.raises(ValueError):
        # noinspection PyTypeChecker
        EAContactsSyncService(
            {'start': '2000--03-25T03:45:00'},
            change_types_cache=change_types_cache,
            data=data,
            ea=mock_ea,
            ea_contacts=mock_ea_contacts,
            entity_fields_cache=entity_fields_cache,
            scheduler=scheduler
        )


def test_code_update(service: EAContactsSyncService) -> None:
    # Test that a ContactUpdate for ActivistCode changes is correctly created.

    update = service._code_update({
        'ActivistCodeID': 1,
        'ChangeTypeID': CREATED_ID,
        'VanID': 2
    })
    assert update.van == 2
    assert update.add_codes == [1]
    assert update.del_codes is None

    update = service._code_update({
        'ActivistCodeID': 3,
        'ChangeTypeID': DELETED_ID,
        'VanID': 4
    })
    assert update.van == 4
    assert update.del_codes == [3]
    assert update.add_codes is None


def test_contact_update(service: EAContactsSyncService) -> None:
    # Test that a ContactUpdate for Contacts changes is correctly created.

    update = service._contact_update({
        'ChangeTypeID': CREATED_OR_UPDATED_ID,
        'DoNotCall': True,
        'DoNotEmail': False,
        'FirstName': 'Alice',
        'LastName': 'Allison',
        'PersonalEmail': 'alice@alice.com',
        'Phone': '1234567890',
        'VanID': 1
    })

    assert update.do_not_call is True
    assert update.do_not_email is False
    assert update.first == 'Alice'
    assert update.last == 'Allison'
    assert update.add_emails == ['alice@alice.com']
    assert update.del_emails is None
    assert update.add_phones == ['1234567890']
    assert update.del_phones is None
    assert update.add_codes is None
    assert update.del_codes is None

    update = service._contact_update({
        'ChangeTypeID': DELETED_ID,
        'DoNotCall': True,
        'DoNotEmail': False,
        'FirstName': 'Alice',
        'LastName': 'Allison',
        'PersonalEmail': 'alice@alice.com',
        'Phone': '1234567890',
        'VanID': 1
    })

    assert update.do_not_call == ''
    assert update.do_not_email == ''
    assert update.first == ''
    assert update.last == ''
    assert update.add_emails is None
    assert update.del_emails == ['alice@alice.com']
    assert update.add_phones is None
    assert update.del_phones == ['1234567890']
    assert update.add_codes is None
    assert update.del_codes is None


def test_install(data: DataDict, service: EAContactsSyncService) -> None:
    # Test EAContactsSyncService.install.

    # Value Error should be raised in absence of _start_time.
    with pytest.raises(ValueError):
        service.install()

    # Test the start time is saved to the DataDict.
    service._start_time = '2000-01-01T03:45:00'
    service.install()
    assert data[service.name] == {'start': '2000-01-01T03:45:00'}
    # noinspection PyUnresolvedReferences
    data._parent.save.assert_called()


def test_start(service: EAContactsSyncService) -> None:
    # Test that EAContactsSyncService.start initializes cached fields to pass to EAClient.changed_entities.changes.

    # Avoid scheduling anything.
    with mock.patch.object(service, '_scheduler', autospec=True):
        service.start()
        assert sorted(service._code_fields, key=lambda x: x.name) == [
            ChangedEntityField(name='ActivistCodeID', type='N'),
            ChangedEntityField(name='ChangeTypeID', type='N'),
            ChangedEntityField(name='VanID', type='N')
        ]

        assert sorted(service._contact_fields, key=lambda x: x.name) == [
            ChangedEntityField(name='ChangeTypeID', type='N'),
            ChangedEntityField(name='DoNotCall', type='B'),
            ChangedEntityField(name='DoNotEmail', type='B'),
            ChangedEntityField(name='FirstName', type='T'),
            ChangedEntityField(name='LastName', type='T'),
            ChangedEntityField(name='PersonalEmail', type='T'),
            ChangedEntityField(name='Phone', type='T'),
            ChangedEntityField(name='VanID', type='N')
        ]
