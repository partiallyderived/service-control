import shlex
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import ClassVar, Final, TypeAlias, TypeVar

import enough as br
import pymongo
from enough import JSONType
from everyaction.objects import ActivistCode, Person
from pymongo import IndexModel, MongoClient, ReturnDocument, UpdateOne
from pymongo.collection import Collection

from servicecontrol.core import Service
from servicecontrol.everyaction.cache import IDNameListCache

# Type of a 'field extractor', consisting of the name of the field in the MongoDB document and a function to parse
# it with.
_FieldExtractor: TypeAlias = tuple[str, Callable[[str], JSONType]]

# Type of sequence of column indexes tupled with activist code IDs.
_ColsAndCodeIDs: TypeAlias = list[tuple[int, int]]

#  Type of sequence of column indexes tupled with _FieldExtractors.
_ColsAndExtractors: TypeAlias = list[tuple[int, _FieldExtractor]]


# Use dataclass to get __init__ and __eq__ for free.
@dataclass
class ContactUpdate:
    """Represents data with which to update a contact document."""

    #: The VAN ID of the contact to update.
    van: int

    #: The first name to update to.
    first: str | None = None

    #: The last name to update to.
    last: str | None = None

    #: The 'Do not call' status to update to.
    do_not_call: bool | None = None

    #: The 'Do not email' status to update to.
    do_not_email: bool | None = None

    #: Emails addresses to add if they are not already present
    add_emails: list[str] | None = None

    #: Email addresses to remove if they are present.
    del_emails: list[str] | None = None

    #: Phone numbers to add if they are not already present.
    add_phones: list[str] | None = None

    #: Phone numbers to remove if they are present.
    del_phones: list[str] | None = None

    #: IDs of activist codes to apply if they are not already applied.
    add_codes: list[int] | None = None

    #: IDs of activist codes to remove if they are applied.
    del_codes: list[int] | None = None

    @staticmethod
    def from_person(person: Person) -> 'ContactUpdate':
        """Creates a ContactUpdate from a Person, using the non-None Person attributes to set corresponding fields in
        the MongoDB document.

        :param person: Person to create update with.
        :return: The resulting ContactUpdate.
        """
        van = person.id
        if van is None:
            raise ValueError('VAN ID required to create ContactUpdate from Person.')
        return ContactUpdate(
            van,
            first=person.first,
            last=person.last,
            do_not_call=person.do_not_call,
            do_not_email=person.do_not_email,
            add_emails=[e.email for e in person.emails],
            add_phones=[p.number for p in person.phones]
        )

    def _update(self) -> JSONType:
        # Get the update dict to pass to MongoDB.
        update = {}
        fields_to_set = {}
        fields_to_unset = set()
        elements_to_add = {}
        elements_to_remove = {}
        for attr in {'first', 'last', 'do_not_call', 'do_not_email'}:
            value = getattr(self, attr)
            if value not in {'', None}:
                fields_to_set[attr] = value
            elif value == '':
                # Delete fields set to empty string.
                fields_to_unset.add(attr)
        for attr in {'add_emails', 'add_phones', 'add_codes'}:
            value = getattr(self, attr)
            if value:
                key = attr[4:]  # Strip 'add_'.
                elements_to_add[key] = value
        for attr in {'del_emails', 'del_phones', 'del_codes'}:
            value = getattr(self, attr)
            if value:
                key = attr[4:]  # Strip 'del_'.
                elements_to_remove[key] = value
        if fields_to_set:
            update['$set'] = fields_to_set
        if fields_to_unset:
            update['$unset'] = {k: "" for k in fields_to_unset}
        if elements_to_add:
            update['$addToSet'] = {k: {'$each': v} for k, v in elements_to_add.items()}
        if elements_to_remove:
            update['$pullAll'] = elements_to_remove
        return update


class EAContactsService(Service):
    """Service which creates a local database of EveryAction contacts using MongoDB."""

    # Unconstrained type variable.
    _T = TypeVar('_T')

    @staticmethod
    def _extract_suppression(value: str) -> bool:
        # Load a suppression like 'Do not call', which is labeled as either 0 or 1.
        return bool(int(value))

    @staticmethod
    def _wrap_in_list(value: str) -> list[str] | None:
        # Wrap a string in a list unless it is the empty string, in which case 'None' is returned.
        return [value] if value else None

    # Mapping from export header name to its corresponding extractor. _identity is used as the parser when the raw
    # value for the field should be used.
    _HEADER_TO_EXTRACTOR: ClassVar[dict[str, _FieldExtractor] | None] = None

    #: The default name to give to the MongoDB collection of EveryAction contacts.
    DEFAULT_COLLECTION_NAME: Final[str] = 'contacts'

    #: The default name to give to the MongoDB database of EveryAction contacts.
    DEFAULT_DATABASE_NAME: Final[str] = 'ea_contact_data'

    EXPORTS: Final[frozenset[str]] = frozenset({'ea_contacts'})
    NAME: Final[str] = 'everyaction-contacts'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for EAContactsService.',
        'type': 'object',
        'properties': {
            'coll-name': {
                'description': f"Name to use for the database's collection ({DEFAULT_COLLECTION_NAME} by default).",
                'type': 'string'
            },
            'db-name': {
                'description': f'Name to use for the database ({DEFAULT_DATABASE_NAME} by default).',
                'type': 'string'
            }
        },
        'additionalProperties': False
    }

    # Cached Activist Codes.
    _activist_codes_cache: IDNameListCache[ActivistCode]

    # Name of MongoDB collection of contacts.
    _coll_name: str

    # Name of MongoDB database.
    _db_name: str

    # MongoDB client.
    _mongo: MongoClient

    #: The exported contact service (self).
    ea_contacts: 'EAContactsService'

    @staticmethod
    def _code_name(header: str) -> str:
        # Determine when the name of an activist code in a header ends by stripping the trailing parenthesized
        # committee. This parenthetical is preceded by an underscore, so that needs to be stripped too.
        name_end = header.rfind('(') - 1
        return header[:name_end]

    @staticmethod
    def _find_query(
        first: str | None = None,
        last: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        codes: Sequence[int] | None = None
    ) -> JSONType:
        # Construct a find query with the given arguments.
        query = {k: v for k, v in {
            'first': first,
            'last': last,
            'emails': email,
            'phones': phone
        }.items() if v}
        if codes:
            query['codes'] = {'$all': codes}
        return query

    @staticmethod
    def _line_to_doc(
        line: str,
        cols_and_extractors: _ColsAndExtractors,
        cols_and_code_ids: _ColsAndCodeIDs
    ) -> JSONType:
        # Parse a line of expected data into a contact document in MongoDB.
        doc = {}
        codes = []
        splits = line.split('\t')

        # Iterate over extractors to parse values which are not related to activist codes.
        for col, extractor in cols_and_extractors:
            field_name, parser = extractor
            raw = splits[col]
            if raw:  # Ignore empty fields.
                value = parser(splits[col])
                # Need to allow values like False and 0.
                if value is not None and value != '':
                    doc[field_name] = value

        # Iterate over activist codes.
        for col, code_id in cols_and_code_ids:
            if splits[col] == 'x':  # A lowercase "x" in an activist code column means that code is applied.
                codes.append(code_id)

        # Add codes even if it is empty.
        doc['codes'] = codes

        # Ensure emails and phones are added if absent.
        doc.setdefault('emails', [])
        doc.setdefault('phones', [])
        return doc

    def _init_indexes(self) -> None:
        # Initialize the MongoDB indexes.
        self.collection.create_indexes([
            IndexModel([('van', pymongo.ASCENDING)], unique=True),
            IndexModel([('first', pymongo.ASCENDING), ('last', pymongo.ASCENDING)], sparse=True),
            IndexModel([('last', pymongo.ASCENDING)], sparse=True),
            IndexModel([('emails', pymongo.ASCENDING)]),
            IndexModel([('phones', pymongo.ASCENDING)]),
            IndexModel([('codes', pymongo.ASCENDING)])
        ])

    def _load_contacts(self, path: str) -> None:
        # Load the initial contacts.
        docs = []
        with open(path) as f:
            # Don't strip tabs, they separate fields.
            header = f.readline().strip(' \n')
            cols_and_extractors, cols_and_code_ids = self._process_header(header)

            for line in f:
                line = line.strip(' \n')
                if line:
                    docs.append(self._line_to_doc(line, cols_and_extractors, cols_and_code_ids))
        self.collection.insert_many(docs)

    def _process_header(self, header_line: str) -> tuple[_ColsAndExtractors, _ColsAndCodeIDs]:
        # Process a header to create _ColsAndExtractors and _ColsAndCodeIDs objects needs by _line_to_doc.
        if not self._activist_codes_cache.resources:
            self._activist_codes_cache.refresh()
        activist_codes = self._activist_codes_cache.resources.values()
        name_to_code = {c.name.replace(' ', '_'): c for c in activist_codes}
        headers = header_line.split('\t')
        cols_and_extractors = []
        cols_and_code_ids = []
        missing_code_names = []
        for i, header in enumerate(headers):
            extractor = self._HEADER_TO_EXTRACTOR.get(header)
            if extractor:
                cols_and_extractors.append((i, extractor))
            elif header.endswith(')'):
                code_name = self._code_name(header)
                code = name_to_code.get(code_name)
                if not code:
                    # Detect all unrecognized codes before printing an error message.
                    missing_code_names.append(code_name)
                else:
                    cols_and_code_ids.append((i, code.id))
        if missing_code_names:
            raise ValueError(
                f'Could not find the following activist codes in EveryAction: {", ".join(missing_code_names)}'
            )
        return cols_and_extractors, cols_and_code_ids

    def __init__(
        self,
        config: JSONType,
        activist_codes_cache: IDNameListCache[ActivistCode],
        mongo: MongoClient
    ) -> None:
        """Initializes this service with the given config and dependencies.

        :param config: Config to initialize with.
        :param activist_codes_cache: Cache of activist codes to use to load them from a contact export file.
        :param mongo: MongoDB client to initialize with.
        """
        super().__init__(config)
        self._activist_codes_cache = activist_codes_cache
        self._coll_name = config.get('coll-name', self.DEFAULT_COLLECTION_NAME)
        self._db_name = config.get('db-name', self.DEFAULT_DATABASE_NAME)
        self._mongo = mongo
        self.ea_contacts = self

    @property
    def collection(self) -> Collection:
        """Gives the MongoDB collection of contacts.

        :return: The collection of contacts.
        """
        return self._mongo[self._db_name][self._coll_name]

    def find(
        self,
        *,
        first: str | None = None,
        last: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        codes: Sequence[int] | None = None
    ) -> list[JSONType]:
        """Finds all contacts with information matching all of the given filters.

        :param first: First name to filter contacts with.
        :param last: Last name to filter contacts with.
        :param email: Email address to filter contacts with.
        :param phone: Phone number to filter contacts with.
        :param codes: Activist codes which must apply to the found contacts.
        :return: The resulting contacts.
        :raise ValueError: If no arguments are given.
        """
        query = self._find_query(first=first, last=last, email=email, phone=phone, codes=codes)
        if not query:
            raise ValueError('At least one argument must be specified for find.')
        cursor = self.collection.find(query, projection={'_id': False})
        return list(cursor)

    def get(self, van: int) -> JSONType | None:
        """Gets a contact using their VAN ID.

        :param van: VAN ID of contact to get.
        :return: The found contact, or :code:`None` if no contact could be found.
        """
        return self.collection.find_one({'van': van}, projection={'_id': False})

    def install(self) -> None:
        """Installs this service's persistent data by creating the necessary MongoDB indices."""
        self._init_indexes()

    def installed(self) -> bool:
        """Determines whether this service is installed.

        :return: :code:`True` if this service is installed, :code:`False` otherwise.
        """
        return len(self.collection.index_information()) > 1

    def job(self, *args: str) -> None:
        """Runs a job on this service. Currently only supports loading exported contact data with two arguments:
        load <file name>.

        :param args: The arguments to run the job with (load and then the file name).
        """
        num_args = len(args)
        if num_args != 2:
            raise ValueError(f'Expected exactly two arguments, found {num_args}: {shlex.join(args)}')
        command, path = args
        if command != 'load':
            raise ValueError(f'Only "load" command is supported, found "{command}"')
        self._load_contacts(path)

    def purge(self) -> None:
        """Deletes all contact data in the MongoDB database."""
        self._mongo.drop_database(self._db_name)

    def update(self, data: ContactUpdate) -> JSONType:
        """Updates a contact with the given data or creates a new contact if it did not already exist.

        :param data: Data to update with.
        :return: The updated contact.
        """
        return self.collection.find_one_and_update(
            {'van': data.van},
            data._update(),
            projection={'_id': False},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

    def update_many(self, data: Iterable[ContactUpdate]) -> None:
        """Updates many contacts, creating those that did not already exist.

        :param data: The updates to apply.
        """
        requests = [UpdateOne({'van': d.van}, d._update(), upsert=True) for d in data]
        self.collection.bulk_write(requests, ordered=False)


EAContactsService._HEADER_TO_EXTRACTOR = {
    'VANID': ('van', int),
    'First': ('first', br.identity),
    'Last': ('last', br.identity),
    'NoCall': ('do_not_call', EAContactsService._extract_suppression),
    'NoEmail': ('do_not_email', EAContactsService._extract_suppression),
    'Preferred Email': ('emails', EAContactsService._wrap_in_list),
    'Preferred Phone': ('phones', EAContactsService._wrap_in_list)
}
