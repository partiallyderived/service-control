import sched
from collections.abc import Sequence
from typing import Final

from enough import JSONType
from everyaction.objects import ActivistCode
from googleapiclient.discovery import Resource

from servicecontrol.core import Service
from servicecontrol.everyaction.cache import CacheProto
from servicecontrol.everyaction.contacts import EAContactsService


class EASheetSyncService(Service):
    """Service which syncs google sheets to contact information according to who
    has a particular Activist Code.
    """

    # The background RGB values for a cell which has suppressed data
    # (e.g., 'Do Not Call').
    _SUPPRESSION_COLORS: Final[tuple[float, float, float]] = (
        0.996, 0.212, 0.212
    )

    #: The amount of time in seconds to wait before two successive syncs by
    # default.
    DEFAULT_PERIOD: Final[int] = 3600

    NAME: Final[str] = 'everyaction-sheetsync'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for EASheetSyncService.',
        'type': 'object',
        'properties': {
            'code-to-sheet': {
                'description':
                    'Mapping from Activist Code names to the sheet they should'
                    'sync to.',
                'type': 'object',
                'additionalProperties': {'type': 'string'}
            },
            'period': {
                'description':
                    'Time in seconds to wait between two successive syncs'
                    '(1 hour by default).',
                'type': 'integer'
            }
        },
        'required': ['code-to-sheet'],
        'additionalProperties': False
    }

    # Mapping from Activist code IDs to the ID of the Google sheet to sync with.
    _code_to_sheet: dict[int, str]

    # Database of EveryAction contacts to use.
    _contacts: EAContactsService

    # Period between two successive syncs.
    _period: int

    # Scheduler to use to schedule syncing.
    _scheduler: sched.scheduler

    # Google Sheet API object.
    _sheets: Resource

    @staticmethod
    def _add_suppression_color(cell: JSONType) -> None:
        # Helper function to add a red background for information which has a
        # suppression.
        cell['userEnteredFormat'] = {
            'backgroundColor': {
                'red': EASheetSyncService._SUPPRESSION_COLORS[0],
                'blue': EASheetSyncService._SUPPRESSION_COLORS[1],
                'green': EASheetSyncService._SUPPRESSION_COLORS[2]
            }
        }

    @staticmethod
    def _sheet_str_row(*values: str) -> JSONType:
        # Helper function to create the proper JSON for user-entered values in a
        # Google sheet given 1 or more values.
        return {
            'values': [{'userEnteredValue': {'stringValue': v}} for v in values]
        }

    def _schedule_update(self) -> None:
        # Update the sheets and schedule the next update.
        self._update_sheets()
        self._scheduler.enter(self._period, 1, self._schedule_update)

    def _update_sheet(
        self, sheet_id: str, contacts: Sequence[JSONType]
    ) -> None:
        # Update the spreadsheet with the given ID to contain the given
        # contacts.
        rows = [self._sheet_str_row('First', 'Last', 'Email', 'Phone')]
        for c in contacts:
            row = self._sheet_str_row(
                c.get('first', ''),
                c.get('last', ''),
                c['emails'][0] if c['emails'] else '',
                c['phones'][0] if c['phones'] else ''
            )
            if c.get('do_not_call'):
                # Add red background to phone number cell.
                self._add_suppression_color(row['values'][-1])
            if c.get('do_not_email'):
                # Add red background to email cell.
                self._add_suppression_color(row['values'][-2])
            rows.append(row)
        self._sheets.batchUpdate(spreadsheetId=sheet_id, body={
            'requests': [{
                'updateCellsRequest': {
                    'rows': rows,
                    'start': {
                        'sheetId': 0,
                        'rowIndex': 0,
                        'columnIndex': 0
                    }
                }
            }]
        }).execute()

    def _update_sheets(self) -> None:
        # Update each spreadsheet.

        # More efficient to get all needed contacts once instead of getting them
        # for each code that applies to them.
        all_contacts = self._contacts.find(
            codes=list(self._code_to_sheet.keys())
        )
        code_to_contacts = {c: [] for c in self._code_to_sheet}
        for contact in all_contacts:
            for code in contact['codes']:
                if code in code_to_contacts:
                    code_to_contacts[code].append(contact)
        for code, sheet_id in self._code_to_sheet.items():
            self._update_sheet(sheet_id, code_to_contacts[code])

    def __init__(
        self,
        config: JSONType,
        activist_code_cache: CacheProto[int | str, ActivistCode],
        ea_contacts: EAContactsService,
        google_sheets: Resource,
        scheduler: sched.scheduler
    ) -> None:
        """Initializes this service from the given config and dependencies.

        :param config: Config to initialize with.
        :param activist_code_cache: Cached activist codes to use to get Activist
            code information.
        :param ea_contacts: The database of EveryAction contacts to get contact
            information from.
        :param google_sheets: The Google Sheets API resource.
        :param scheduler: The scheduler to use to schedule sheet syncing.
        """
        super().__init__(config)
        self._code_to_sheet = {
            activist_code_cache[k].id: v
            for k, v in config['code-to-sheet'].items()
        }
        self._period = config.get('period', self.DEFAULT_PERIOD)

        self._contacts = ea_contacts
        self._scheduler = scheduler
        self._sheets = google_sheets

    def start(self) -> None:
        """Starts scheduling Google Sheet syncs."""
        # Do it this way so start terminates before the spreadsheets need to be
        # updated.
        self._scheduler.enter(0.01, 1, self._schedule_update)
