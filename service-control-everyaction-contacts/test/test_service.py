import copy
import unittest.mock as mock
from tempfile import NamedTemporaryFile
from unittest.mock import Mock

import enough
import pymongo
import pytest
from enough import JSONType
from everyaction.objects import ActivistCode, Person
from mongomock import MongoClient

from servicecontrol.everyaction.cache import IDNameListCache
from servicecontrol.everyaction.contacts import ContactUpdate, EAContactsService


# ----- Test ContactUpdate -----


def test_contact_update() -> None:
    # Test that a ContactUpdate object produces the correct MongoDB query.

    update = ContactUpdate(3, first='Alice', last='Simpson', do_not_email=True)
    assert update._update() == {
        '$set': {'first': 'Alice', 'last': 'Simpson', 'do_not_email': True}
    }

    # Empty strings should unset.
    update.first = ''
    update.last = ''
    assert update._update() == {
        '$set': {'do_not_email': True}, '$unset': {'first': '', 'last': ''}
    }

    update.first = 'Alice'
    update.add_codes = [123, 456, 789]
    update.del_codes = [111, 222]
    update.add_emails = ['example@example.com', 'fake@fake.com']
    update.del_emails = ['what@now.com', 'keep@on.com']
    update.add_phones = ['1234567890', '5555555555']
    update.del_phones = ['9876543210']
    update.do_not_call = False
    assert update._update() == {
        '$addToSet': {
            'codes': {'$each': [123, 456, 789]},
            'emails': {'$each': ['example@example.com', 'fake@fake.com']},
            'phones': {'$each': ['1234567890', '5555555555']}
        },
        '$pullAll': {
            'codes': [111, 222],
            'emails': ['what@now.com', 'keep@on.com'],
            'phones': ['9876543210']
        },
        '$set': {
            'first': 'Alice',
            'do_not_email': True,
            'do_not_call': False
        },
        '$unset': {'last': ''}
    }


def test_from_person() -> None:
    # Test that ContactUpdate.from_person correct transforms a Person object
    # into a MongoDB contact document.

    emails_to_add = ['example@example.com', 'fake@fake.com']
    phones_to_add = ['1234567890', '5555555555']
    assert ContactUpdate.from_person(
        Person(
            id=1,
            first='First',
            last='Last',
            do_not_email=True,
            do_not_call=False,
            emails=emails_to_add,
            phones=phones_to_add
        )
    ) == ContactUpdate(
        1,
        first='First',
        last='Last',
        do_not_email=True,
        do_not_call=False,
        add_emails=emails_to_add,
        add_phones=phones_to_add
    )

    # Test that failure to specify ID results in a ValueError.
    with pytest.raises(ValueError, match=r'VAN ID required'):
        ContactUpdate.from_person(Person(first='First'))


# ----- Test EAContactsService Static Methods -----

def test_code_name() -> None:
    # Test that _code_name correctly strips the committee off a header for an
    # activist code.

    assert EAContactsService._code_name(
        'Some_Activist_(Atlanta)'
    ) == 'Some_Activist'


def test_extract_suppression() -> None:
    # That that _extract_suppression correctly converts 0 and 1 to False and
    # True respectively.

    assert EAContactsService._extract_suppression('0') is False
    assert EAContactsService._extract_suppression('1') is True


def test_find_query() -> None:
    # Test that _find_query correctly constructs a query with the appropriate
    # arguments.
    assert EAContactsService._find_query(
        first='Alice',
        last='Allison',
        email='alice@alice.com',
        phone='1234567890',
        codes=[1, 4, 9]
    ) == {
        'first': 'Alice',
        'last': 'Allison',
        'emails': 'alice@alice.com',
        'phones': '1234567890',
        'codes': {'$all': [1, 4, 9]}
    }

    assert EAContactsService._find_query(first='Alice') == {'first': 'Alice'}


def test_line_to_doc() -> None:
    # Test various cases of the usage of _line_to_doc to check that a single
    # line is correctly parsed.

    cols_and_extractors = [
        (0, ('int', int)),
        (1, ('emails', lambda x: [x])),
        (3, ('phones', lambda x: [x]))
    ]

    cols_and_code_ids = [
        (2, 9),
        (4, 15)
    ]

    # Try with all nonempty fields.
    assert EAContactsService._line_to_doc(
        '3\tfake@fake.com\tx\t1234567890\tx',
        cols_and_extractors,
        cols_and_code_ids
    ) == {
        'int': 3,
        'emails': ['fake@fake.com'],
        'phones': ['1234567890'],
        'codes': [9, 15]
    }

    # Try with some empty fields. Note that codes, phones, and emails should
    # always be set.
    assert EAContactsService._line_to_doc(
        '\tfake@fake.com\tx\t\t', cols_and_extractors, cols_and_code_ids
    ) == {
        'emails': ['fake@fake.com'],
        'phones': [],
        'codes': [9]
    }

    # Try with all empty fields.
    assert EAContactsService._line_to_doc(
        '\t\t\t\t', cols_and_extractors, cols_and_code_ids
    ) == {
        'codes': [],
        'emails': [],
        'phones': []
    }


def test_wrap_in_list() -> None:
    # Test that _wrap_in_list correctly wraps non-empty strings in lists or else
    # returns None.
    assert EAContactsService._wrap_in_list('a') == ['a']
    assert EAContactsService._wrap_in_list('') is None


# ----- Test EAContactsService Instance Methods ----- #


@pytest.fixture
def alice_doc() -> JSONType:
    # A document for a contact named Alice.
    return {
        'van': 1,
        'first': 'Alice',
        'last': 'Allison',
        'emails': ['alice1@alice.com', 'alice2@alice.com'],
        'phones': ['1234567890', '5555555555'],
        'do_not_call': False,
        'do_not_email': True,
        'codes': [1, 2, 3]
    }


@pytest.fixture
def alice_update(alice_doc: JSONType) -> ContactUpdate:
    # A ContactUpdate that, when used to create a document, results in
    # alice_doc.
    return ContactUpdate(
        1,
        first=alice_doc['first'],
        last=alice_doc['last'],
        add_emails=alice_doc['emails'],
        del_emails=['alice3@alice.com', 'alice4@alice.com'],
        add_phones=alice_doc['phones'],
        del_phones=['9876543210', '0000000000'],
        do_not_call=alice_doc['do_not_call'],
        do_not_email=alice_doc['do_not_email'],
        add_codes=alice_doc['codes'],
        del_codes=[4, 5, 6]
    )


@pytest.fixture
def bob_doc() -> JSONType:
    # A document for a contact named Bob.
    return {
        'van': 2,
        'first': 'Bob',
        'last': 'Rob',
        'emails': ['bob@bob.com'],
        'codes': [1, 8, 27]
    }


@pytest.fixture
def bob_update(bob_doc: JSONType) -> ContactUpdate:
    # A ContactUpdate that, when used to create a document, results in bob_doc.
    return ContactUpdate(
        2,
        first=bob_doc['first'],
        last=bob_doc['last'],
        add_emails=bob_doc['emails'],
        add_codes=bob_doc['codes']
    )


@pytest.fixture
def mock_code_cache() -> Mock:
    # Create a mock IDNameListCache to use for cached activist codes.
    result = Mock(spec=IDNameListCache)
    result.resources = {}
    return result


@pytest.fixture
def mongo_mock() -> MongoClient:
    # Create a mock MongoClient to simulate the contact database.
    return MongoClient()


def test_init(mock_code_cache: Mock, mongo_mock: MongoClient) -> None:
    # Test initialization of an EAContactsService object.

    # Empty config should be OK.
    service = EAContactsService(
        {}, activist_codes_cache=mock_code_cache, mongo=mongo_mock
    )
    assert service._activist_codes_cache == mock_code_cache
    assert service._coll_name == EAContactsService.DEFAULT_COLLECTION_NAME
    assert service._db_name == EAContactsService.DEFAULT_DATABASE_NAME
    assert service._mongo == mongo_mock
    assert service.ea_contacts is service

    # Specify collection name, database name, and path to initial contacts.
    service = EAContactsService({
        'coll-name': 'my-collection',
        'db-name': 'my-db'
    }, mock_code_cache, mongo_mock)

    assert service._coll_name == 'my-collection'
    assert service._db_name == 'my-db'


@pytest.fixture
def service(
    mock_code_cache: Mock, mongo_mock: MongoClient
) -> EAContactsService:
    # Create an instance of the service for testing.
    return EAContactsService({
        'coll-name': 'my-collection',
        'db-name': 'my-db',
        'init-contacts': 'path-to-contacts.txt'
    }, mock_code_cache, mongo_mock)


def test_init_indexes(service: EAContactsService) -> None:
    # Ensure that indexes are initialized correctly.
    service._init_indexes()
    index_info = list(service.collection.index_information().values())
    for info in index_info:
        # Some of the values for 'key' are dict_items instead of straight lists.
        info['key'] = list(info['key'])
        del info['v']
    index_info = sorted(index_info, key=lambda x: x['key'][0][0])
    assert index_info == [
        {'key': [('_id', pymongo.ASCENDING)]},
        {'key': [('codes', pymongo.ASCENDING)]},
        {'key': [('emails', pymongo.ASCENDING)]},
        {'key': [
            ('first', pymongo.ASCENDING),
            ('last', pymongo.ASCENDING)
        ], 'sparse': True},
        {'key': [('last', pymongo.ASCENDING)], 'sparse': True},
        {'key': [('phones', pymongo.ASCENDING)]},
        {'key': [('van', pymongo.ASCENDING)], 'unique': True}
    ]


def test_load_contacts(service: EAContactsService) -> None:
    # Test that load contacts correctly processes an exported contacts file and
    # delegates logic to helper functions.
    with NamedTemporaryFile('w') as f:
        header = (
            'VANID\tFirst\tLast\tActivist_Code1_(Committee)\t'
            'Activist_Code2_(Committee)'
        )
        line1 = '1\tAlice\tAllison\tx\t'
        line2 = '2\tBob\tBobbington\t\t'
        line3 = '3\tCarl\tCarlson\tx\tx'
        f.write(f'{header}\n{line1}\n{line2}\n{line3}\n')
        f.flush()

        with mock.patch.multiple(
            service,
            autospec=True,
            _line_to_doc=mock.DEFAULT,
            _process_header=mock.DEFAULT
        ) as mocks:
            mock_line_to_doc = mocks['_line_to_doc']
            mock_line_to_doc.side_effect = [
                {'name': 'Alice'},
                {'name': 'Bob'},
                {'name': 'Cody'}
            ]
            mock_process_header = mocks['_process_header']
            mock_cols_and_extractors = Mock()
            mock_cols_and_code_ids = Mock()
            mock_process_header.return_value = (
                mock_cols_and_extractors, mock_cols_and_code_ids
            )
            service._load_contacts(f.name)
            mock_process_header.assert_called_with(header)
            assert mock_line_to_doc.call_args_list == [
                mock.call(
                    line1, mock_cols_and_extractors, mock_cols_and_code_ids
                ),
                mock.call(
                    line2, mock_cols_and_extractors, mock_cols_and_code_ids
                ),
                mock.call(
                    line3, mock_cols_and_extractors, mock_cols_and_code_ids
                )
            ]
        assert service.collection.count_documents({}) == 3
        assert list(service.collection.find(
            {'name': 'Alice'}, projection={'_id': False}
        )) == [{'name': 'Alice'}]
        assert list(service.collection.find(
            {'name': 'Bob'}, projection={'_id': False}
        )) == [{'name': 'Bob'}]
        assert list(service.collection.find(
            {'name': 'Cody'}, projection={'_id': False}
        )) == [{'name': 'Cody'}]


def test_process_header(
    service: EAContactsService, mock_code_cache: Mock
) -> None:
    # Test various cases of _process_header.

    # First try with all fields.
    mock_code_cache.resources['Activist Code1'] = ActivistCode(
        id=1, name='Activist Code1'
    )
    mock_code_cache.resources['Activist Code2'] = ActivistCode(
        id=2, name='Activist Code2'
    )
    cols_and_extractors, cols_and_code_ids = service._process_header(
        'VANID\tFirst\tLast\tNoCall\tActivist_Code1_(Committee)\tNoEmail\t'
        'Activist_Code2_(Committee)\tExtraneous\tPreferred Phone\t'
        'Preferred Email'
    )
    assert cols_and_extractors == [
        (0, ('van', int)),
        (1, ('first', enough.identity)),
        (2, ('last', enough.identity)),
        (3, ('do_not_call', EAContactsService._extract_suppression)),
        (5, ('do_not_email', EAContactsService._extract_suppression)),
        (8, ('phones', EAContactsService._wrap_in_list)),
        (9, ('emails', EAContactsService._wrap_in_list))
    ]
    assert cols_and_code_ids == [(4, 1), (6, 2)]

    # Now try with some missing fields.
    cols_and_extractors, cols_and_code_ids = service._process_header(
        'VANID\tFirst\tLast\tActivist_Code1_(Committee)'
    )
    assert cols_and_extractors == [
        (0, ('van', int)),
        (1, ('first', enough.identity)),
        (2, ('last', enough.identity))
    ]
    assert cols_and_code_ids == [(3, 1)]

    # Try with no activist codes.
    cols_and_extractors, cols_and_code_ids = service._process_header(
        'VANID\tFirst\tLast'
    )
    assert cols_and_extractors == [
        (0, ('van', int)),
        (1, ('first', enough.identity)),
        (2, ('last', enough.identity))
    ]
    assert cols_and_code_ids == []

    # Try with missing activist codes.
    with pytest.raises(
        ValueError,
        match=(
            r'Could not find the following activist codes in EveryAction: '
            r'Activist_Code3, Activist_Code4'
        )
    ):
        service._process_header(
            'VANID\tFirst\tLast\tActivist_Code1_(Committee)\t'
            'Activist_Code2_(Committee)\tActivist_Code3_(Committee)\t'
            'Activist_Code4_(Committee)'
        )


def test_collection(service: EAContactsService) -> None:
    # Test that the collection property works.
    assert service.collection is service._mongo[service._db_name][
        service._coll_name
    ]


def test_find(
    service: EAContactsService, alice_doc: JSONType, bob_doc: JSONType
) -> None:
    # Test that find actually finds the correct documents based on various
    # queries.

    # Use another Alice doc to test find on first name when multiple people have
    # the same first name.
    alice_doc2 = {
        'van': 3,
        'first': 'Alice',
        'last': 'Alice',
        'emails': [],
        'phones': [],
        'codes': [1, 4, 9]
    }
    # Need to copy since PyMongo mutates documents without an _id field.
    service.collection.insert_many([
        copy.deepcopy(alice_doc),
        copy.deepcopy(alice_doc2),
        copy.deepcopy(bob_doc)
    ])

    assert service.find(first='Alice') == [alice_doc, alice_doc2]
    assert service.find(last='Allison') == [alice_doc]
    assert service.find(email='alice1@alice.com') == [alice_doc]
    assert service.find(email='alice2@alice.com') == [alice_doc]
    assert service.find(phone='1234567890') == [alice_doc]
    assert service.find(phone='5555555555') == [alice_doc]
    assert service.find(codes=[1, 8]) == [bob_doc]
    assert service.find(codes=[1]) == [alice_doc, alice_doc2, bob_doc]

    # Check that failure to pass any arguments results in a ValueError.
    with pytest.raises(
        ValueError,
        match=r'At least one argument must be specified for find\.'
    ):
        service.find()


def test_get(
    service: EAContactsService, alice_doc: JSONType, bob_doc: JSONType
) -> None:
    # Test that get can find a contact with the given VAN ID.
    service.collection.insert_many([
        copy.deepcopy(alice_doc), copy.deepcopy(bob_doc)
    ])
    assert service.get(1) == alice_doc
    assert service.get(2) == bob_doc
    assert service.get(3) is None


def test_install(service: EAContactsService) -> None:
    # Test that this service is installed correctly.

    # Test that indexes are initialized.
    with mock.patch.object(
        service, '_init_indexes', autospec=True
    ) as mock_init_indexes:
        service.install()
        mock_init_indexes.assert_called_with()


def test_installed(service: EAContactsService) -> None:
    # Test that installation state is correctly determined.

    # Need installation by default.
    assert not service.installed()

    # When indexes are added, installation is not needed.
    service._init_indexes()
    assert service.installed()


def test_job(service: EAContactsService) -> None:
    # Test that job can be used to load contacts.
    with mock.patch.object(service, '_load_contacts') as mock_load:
        service.job('load', 'contacts.txt')
        mock_load.assert_called_with('contacts.txt')

    # Test that exactly two args needed.
    with pytest.raises(ValueError):
        service.job('load')

    with pytest.raises(ValueError):
        service.job('load', 'contacts1.txt', 'contacts2.txt')

    # Test that first argument must be load.
    with pytest.raises(ValueError):
        service.job('save', 'contacts1.txt')


def test_purge(service: EAContactsService) -> None:
    # Test that purge deletes the contacts database.
    service.install()
    assert service._db_name in service._mongo.list_database_names()
    service.purge()
    assert service._db_name not in service._mongo.list_database_names()


def test_update(
    service: EAContactsService,
    alice_doc: JSONType,
    alice_update: ContactUpdate,
    bob_doc: JSONType,
    bob_update: ContactUpdate
) -> None:
    # Check that update updates a contact with new data or creates a contact if
    # it could not be found.

    assert service.update(alice_update) == alice_doc

    # Check that document is actually in collection.
    assert service.get(1) == alice_doc
    assert service.update(bob_update) == bob_doc

    alice_doc['last'] = 'Malice'
    alice_update = ContactUpdate(1, last='Malice')
    assert service.update(alice_update) == alice_doc

    # Delete some present emails, phones, and codes.
    alice_update.first = 'Allie'
    alice_update.do_not_call = True
    alice_update.do_not_email = False
    alice_update.del_emails = [
        'alice1@alice.com', 'alice2@alice.com', 'alice3@alice.com'
    ]
    alice_update.del_phones = ['5555555555', '2222222222']
    alice_update.del_codes = [1, 3, 5]

    assert service.update(alice_update) == {
        'van': 1,
        'first': 'Allie',
        'last': 'Malice',
        'do_not_call': True,
        'do_not_email': False,
        'emails': [],
        'phones': ['1234567890'],
        'codes': [2]
    }

    # Unset first and last
    alice_update.first = ''
    alice_update.last = ''
    assert service.update(alice_update) == {
        'van': 1,
        'do_not_call': True,
        'do_not_email': False,
        'emails': [],
        'phones': ['1234567890'],
        'codes': [2]
    }


def test_update_many(
    service: EAContactsService,
    alice_doc: JSONType,
    alice_update: ContactUpdate,
    bob_doc: JSONType,
    bob_update: ContactUpdate
) -> None:
    # Check that update_many allows many documents to be created/updated at
    # once.
    service.update_many([alice_update, bob_update])
    assert service.get(1) == alice_doc
    assert service.get(2) == bob_doc

    # Make changes to docs and updates that would produce those changes.
    alice_doc['first'] = 'Alice2'
    alice_update.first = 'Alice2'
    alice_doc['phones'].append('3333333333')
    alice_update.add_phones.append('3333333333')
    alice_update.del_phones.append(alice_doc['phones'][0])
    del alice_doc['phones'][0]

    bob_doc['emails'].append('bob2@bob.com')
    bob_update.add_emails.append('bob2@bob.com')

    # Also add a new doc, so we have a combination of updates and inserts.
    carl_doc = {'van': 3, 'first': 'Carl', 'last': 'Carlson'}
    carl_update = ContactUpdate(3, first='Carl', last='Carlson')

    service.update_many([alice_update, bob_update, carl_update])
    assert service.get(1) == alice_doc
    assert service.get(2) == bob_doc
    assert service.get(3) == carl_doc
