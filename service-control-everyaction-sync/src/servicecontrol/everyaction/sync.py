import sched
from collections.abc import Callable, MutableMapping, MutableSequence
from datetime import datetime
from typing import Final

from enough import JSONType
from everyaction import EAClient
from everyaction.objects import ChangedEntityField, ChangeType

from servicecontrol.core import Service
from servicecontrol.everyaction.cache import CacheProto
from servicecontrol.everyaction.contacts import ContactUpdate, EAContactsService
from servicecontrol.tools.data import DataDict


class EAContactsSyncService(Service):
    """Service which periodically updates EveryAction contact data for
    ``EAContactsService``.
    """
    
    # Names of the 'ContactsActivistCodes' fields to detect changes in.
    _CODE_FIELDS: Final[set[str]] = {'ActivistCodeID', 'ChangeTypeID', 'VanID'}

    # Names of the 'Contacts' fields to detect changes in.
    _CONTACT_FIELDS: Final[set[str]] = {
        'ChangeTypeID',
        'DoNotCall',
        'DoNotEmail',
        'FirstName',
        'LastName',
        'PersonalEmail',
        'Phone',
        'VanID'
    }

    # Handlers setting a ContactUpdate's state when values are being deleted.
    _DELETE_HANDLERS: Final[
        dict[str, Callable[[ContactUpdate, object], None]]
    ] = {
        'DoNotCall': lambda x, _: setattr(x, 'do_not_call', ''),
        'DoNotEmail': lambda x, _: setattr(x, 'do_not_email', ''),
        'FirstName': lambda x, _: setattr(x, 'first', ''),
        'LastName': lambda x, _: setattr(x, 'last', ''),
        'PersonalEmail': lambda x, y: setattr(x, 'del_emails', [y]),
        'Phone': lambda x, y: setattr(x, 'del_phones', [y])
    }

    # Handlers for setting a ContactUpdate's state when values are being created
    # or updated.
    _UPDATE_HANDLERS: Final[
        dict[str, Callable[[ContactUpdate, object], None]]
    ] = {
        'DoNotCall': lambda x, y: setattr(x, 'do_not_call', y),
        'DoNotEmail': lambda x, y: setattr(x, 'do_not_email', y),
        'FirstName': lambda x, y: setattr(x, 'first', y),
        'LastName': lambda x, y: setattr(x, 'last', y),
        'PersonalEmail': lambda x, y: setattr(x, 'add_emails', [y]),
        'Phone': lambda x, y: setattr(x, 'add_phones', [y])
    }

    #: Default value in seconds to use for update period.
    DEFAULT_PERIOD: Final[int] = 3600

    NAME: Final[str] = 'everyaction-sync'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for EAContactsSyncService.',
        'type': 'object',
        'properties': {
            'period': {
                'description':
                    f'Period in seconds between two contact syncs '
                    f'({DEFAULT_PERIOD} by default).',
                'type': 'integer'
            },
            'start': {
                'description':
                    'ISO-formatted date to start contacts sync. Required for '
                    'installation.',
                'type': 'string'
            }
        },
        'additionalProperties': False
    }

    # The cached ChangeType objects.
    _change_types: CacheProto[str, CacheProto[int | str, ChangeType]]

    # The list of ChangedEntityFields to cache for changed entity export job
    # requests on the 'ContactsActivistCode' resource.
    _code_fields: list[ChangedEntityField]

    # The list of ChangedEntityFields to cache for changed entity export job
    # requests on the 'Contacts' resource.
    _contact_fields: list[ChangedEntityField]

    # The service-control data service.
    _data: DataDict

    # The EveryAction client to use to perform updates.
    _ea: EAClient

    # The database of EveryAction contacts to update.
    _ea_contacts: EAContactsService

    # The cached ChangedEntityField objects.
    _fields: CacheProto[str, CacheProto[str, ChangedEntityField]]

    # The configured period.
    _period: int

    # The scheduler to use to schedule updates.
    _scheduler: sched.scheduler

    # The configured start time, if given.
    _start_time: str | None

    def _code_update(
        self, changes: MutableMapping[str, ChangedEntityField.ValueType]
    ) -> ContactUpdate | None:
        # Create a ContactUpdate based on the given Activist Code changes.
        code_id = changes.pop('ActivistCodeID')
        van = changes.pop('VanID')
        change_type_id = changes.pop('ChangeTypeID')
        change_type = self._change_types[
            'ContactsActivistCodes'
        ][change_type_id].name
        update = ContactUpdate(van)
        if change_type == 'Created':
            update.add_codes = [code_id]
            return update
        elif change_type == 'Deleted':
            update.del_codes = [code_id]
            return update
        return None

    def _contact_update(
        self, changes: MutableMapping[str, ChangedEntityField.ValueType]
    ) -> ContactUpdate | None:
        # Create a ContactUpdate based on the given Contact changes.
        van = changes.pop('VanID')
        change_type_id = changes.pop('ChangeTypeID')
        change_type = self._change_types['Contacts'][change_type_id].name
        update = ContactUpdate(van)
        if change_type == 'CreatedOrUpdated':
            for field, value in changes.items():
                self._UPDATE_HANDLERS[field](update, value)
            return update
        elif change_type == 'Deleted':
            for field, value in changes.items():
                self._DELETE_HANDLERS[field](update, value)
            return update
        return None

    def _schedule_update(self) -> None:
        # Update the EveryAction contacts database and then schedule it to be
        # updated again after the configured period.
        self._update()
        self._scheduler.enter(self._period, 1, self._schedule_update)

    def _update(self) -> None:
        # Update the EveryAction contacts database by incorporating changes made
        # since the last update.
        start = self._data[self.name]['start']
        end = datetime.now().isoformat()
        updates = []
        self._update_codes(start, end, updates)
        self._update_contacts(start, end, updates)
        if updates:
            self._ea_contacts.update_many(updates)
        self._data[self.name]['start'] = end
        self._data.save()

    def _update_codes(
        self, start: str, end: str, updates: MutableSequence[ContactUpdate]
    ) -> None:
        # Use a changed-entity export job to update activist codes.
        for changes in self._ea.changed_entities.changes(
            self._code_fields,
            changed_from=start,
            changed_to=end,
            resource='ContactsActivistCodes'
        ):
            update = self._code_update(changes)
            if update is not None:
                updates.append(update)

    def _update_contacts(
        self, start: str, end: str, updates: MutableSequence[ContactUpdate]
    ) -> None:
        # Use a changed-entity export job to update contacts.
        for changes in self._ea.changed_entities.changes(
            self._contact_fields,
            changed_from=start,
            changed_to=end,
            resource='Contacts'
        ):
            update = self._contact_update(changes)
            if update is not None:
                updates.append(update)

    def __init__(
        self,
        config: JSONType,
        change_types_cache: CacheProto[str, CacheProto[int | str, ChangeType]],
        data: DataDict,
        ea: EAClient,
        ea_contacts: EAContactsService,
        entity_fields_cache: CacheProto[
            str, CacheProto[str, ChangedEntityField]
        ],
        scheduler: sched.scheduler
    ) -> None:
        """Initializes this service with the given config and dependencies.

        :param config: Config to initialize with.
        :param change_types_cache: Cached map of resource names to maps of
            IDs/names of change types to ChangeType objects.
        :param data: The data service to store persistent data with.
        :param ea: The EveryAction client to use to perform updates.
        :param ea_contacts: The EveryAction contacts database to update.
        :param entity_fields_cache: Cached map of resource names to maps of
            names of changed entity fields to ChangedEntityField objects.
        :param scheduler: The scheduler to regularly schedule syncs with.
        :raise ValueError: If the date given for 'start' malformed.
        """
        super().__init__(config)
        self._code_fields = []
        self._contact_fields = []
        self._period = config.get('period', self.DEFAULT_PERIOD)
        self._start_time = config.get('start')
        # Check that it's ISO formatted.
        datetime.fromisoformat(self._start_time) if self._start_time else None

        self._change_types = change_types_cache
        self._data = data
        self._ea = ea
        self._ea_contacts = ea_contacts
        self._fields = entity_fields_cache
        self._scheduler = scheduler

    def install(self) -> None:
        """Installs this service by persisting data about when the last sync
        occurred.

        :raise ValueError: If 'start' was not specified in the given config.
        """
        # Use _start_time as 'first last' sync.
        if not self._start_time:
            raise ValueError(
                'The configuration key "start" must be specified on '
                'installation to the time from which to start syncing.'
            )
        data = {'start': self._start_time}
        self._data[self.name] = data
        self._data.save()

    def installed(self) -> bool:
        """Determines if this service needs to be installed by detecting if the
        name of this service is in the data mapping.
        """
        return self.name in self._data

    def purge(self) -> None:
        """Purges this service by deleting its persistent data."""
        del self._data[self.name]
        self._data.save()

    def start(self) -> None:
        """Starts the periodic update-syncing process."""
        self._code_fields = [
            self._fields['ContactsActivistCodes'][x] for x in self._CODE_FIELDS
        ]
        self._contact_fields = [
            self._fields['Contacts'][x] for x in self._CONTACT_FIELDS
        ]

        # Start updating. Entered into the scheduler this way so that updating
        # happens (almost) immediately, but other services need not wait on this
        # service to start.
        self._scheduler.enter(0.01, 1, self._schedule_update)
