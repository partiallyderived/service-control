from collections.abc import (
    Callable, Mapping, MutableMapping, MutableSequence, Sequence
)
from unittest.mock import Mock

import pytest
from everyaction import EAClient
from everyaction.objects import ActivistCode, ChangedEntityField, ChangeType
from everyaction.services import ActivistCodes, ChangedEntities

from servicecontrol.everyaction.cache import (
    EACacheService, IDNameListCache, NameListCache, ResourceNameListCaches
)


@pytest.fixture
def activist_codes() -> list[ActivistCode]:
    # Gives some dummy ActivistCodes to use for testing.
    return [
        ActivistCode(id=1, name='Code 1'),
        ActivistCode(id=2, name='code 2'),
        ActivistCode(id=3, name='CODE 3')
    ]


@pytest.fixture
def activist_codes_list() -> list[ActivistCode]:
    # Returns a list which can be mutated to modify the cache of activist codes.
    return []


@pytest.fixture
def list_fn(
    activist_codes_list: MutableSequence[ActivistCode]
) -> Callable[[], MutableSequence[ActivistCode]]:
    # Returns the contents of activist_codes_list, which may be modified as
    # needed by tests.
    return lambda: activist_codes_list


@pytest.fixture
def resource_to_change_types() -> dict[str, list[ChangeType]]:
    # Provide mapping from resource names to dummy ChangeTypes for testing.
    return {
        'resource 1': [
            ChangeType(id=1, name='type 1')
        ],
        'resource 2': [
            ChangeType(id=2, name='TYPE 2'),
            ChangeType(id=3, name='tYpE 3')
        ],
        'resource 3': [
            ChangeType(id=4, name='tyPE 4'),
            ChangeType(id=5, name='Type 5'),
            ChangeType(id=6, name='TYPe 6')
        ]
    }


@pytest.fixture
def resource_to_change_types_dict() -> dict:
    # Return a dictionary of resource names to sequences of ChangeTypes that can
    # be mutated to modify caches.
    return {}


@pytest.fixture
def resource_to_fields() -> dict[str, list[ChangedEntityField]]:
    # Provide mapping from resource names to dummy ChangedEntityFields for
    # testing.
    return {
        'resource 1': [
            ChangedEntityField(name='field 1')
        ],
        'resource 2': [
            ChangedEntityField(name='FIELD 2'),
            ChangedEntityField(name='field 3')
        ],
        'resource 3': [
            ChangedEntityField(name='field 4'),
            ChangedEntityField(name='Field 5'),
            ChangedEntityField(name='Field 6')
        ]
    }


@pytest.fixture
def resource_to_list_fn(
    resource_to_change_types_dict: MutableMapping[str, Sequence[ChangeType]]
) -> Callable[[str], Sequence[ChangeType]]:
    # Returns the contents of resource_to_change_types_dict, which may be
    # modified as needed by tests.
    return lambda r: resource_to_change_types_dict[r]


def test_name_list_cache(
    activist_codes: Sequence[ActivistCode],
    activist_codes_list: MutableSequence[ActivistCode],
    list_fn: Callable[[], Sequence[ActivistCode]]
) -> None:
    # Test NameListCache class.
    cache = NameListCache(list_fn)
    with pytest.raises(KeyError):
        # noinspection PyStatementEffect
        cache['code 1']
    assert cache.get('code 1') is None

    activist_codes_list.append(activist_codes[0])
    assert cache['code 1'] == activist_codes[0]
    assert cache['CODE 1'] == activist_codes[0]
    assert cache.get('code 2') is None

    activist_codes_list.append(activist_codes[1])
    assert cache['code 2'] == activist_codes[1]
    assert cache['CODE 2'] == activist_codes[1]


def test_id_name_list_cache(
    activist_codes: Sequence[ActivistCode],
    activist_codes_list: MutableSequence[ActivistCode],
    list_fn: Callable[[], Sequence[ActivistCode]]
) -> None:
    # Test IDNameListCache class.
    cache = IDNameListCache(list_fn)
    with pytest.raises(KeyError):
        # noinspection PyStatementEffect
        cache[1]
    assert cache.get('code 1') is None

    activist_codes_list.append(activist_codes[0])
    assert cache['code 1'] == activist_codes[0]
    assert cache['CODE 1'] == activist_codes[0]
    assert cache[1] == activist_codes[0]
    assert cache.get('code 2') is None
    assert cache.get(2) is None

    activist_codes_list.append(activist_codes[2])
    assert cache['code 3'] == activist_codes[2]
    assert cache['CODE 3'] == activist_codes[2]
    assert cache[3] == activist_codes[2]


def test_resource_name_list_caches(
    resource_to_change_types: Mapping[str, Sequence[ChangeType]],
    resource_to_change_types_dict: MutableMapping[str, Sequence[ChangeType]],
    resource_to_list_fn: Callable[[str], Sequence[ChangeType]]
) -> None:
    # Test ResourceNameListCaches class.
    # noinspection PyTypeChecker
    caches = ResourceNameListCaches(
        lambda r: r in resource_to_change_types_dict,
        lambda r: IDNameListCache(lambda: resource_to_list_fn(r))
    )
    with pytest.raises(KeyError):
        # noinspection PyStatementEffect
        caches['resource 1']

    resource_to_change_types_dict[
        'resource 1'
    ] = resource_to_change_types['resource 1']
    assert caches['resource 1'][1] == resource_to_change_types['resource 1'][0]
    assert caches['resource 1']['type 1'] == resource_to_change_types[
        'resource 1'
    ][0]
    assert caches['resource 1'].get('type 2') is None
    assert caches.get('resource 2') is None

    resource_to_change_types_dict['resource 2'] = resource_to_change_types[
        'resource 2'
    ]
    assert caches['resource 1'].get(2) is None
    assert caches['resource 2'].get('type 1') is None
    assert caches['resource 2']['type 2'] == resource_to_change_types[
        'resource 2'
    ][0]
    assert caches['resource 2'][3] == resource_to_change_types['resource 2'][1]


def test_service(
    activist_codes: Sequence[ActivistCode],
    resource_to_change_types: Mapping[str, Sequence[ChangeType]],
    resource_to_fields: Mapping[str, Sequence[ChangedEntityField]]
) -> None:
    # Tests that the service caches what it is expected to.
    mock_ea = Mock(spec=EAClient)

    mock_ea.activist_codes = Mock(spec=ActivistCodes)
    mock_ea.activist_codes.list.return_value = activist_codes

    mock_ea.changed_entities = Mock(spec=ChangedEntities)
    mock_ea.changed_entities.resources.return_value = list(
        resource_to_change_types.keys()
    )

    def change_types_fn(resource: str) -> Sequence[ChangeType]:
        return resource_to_change_types[resource]

    def fields_fn(resource: str) -> Sequence[ChangedEntityField]:
        return resource_to_fields[resource]

    mock_ea.changed_entities.change_types = change_types_fn
    mock_ea.changed_entities.fields = fields_fn

    service = EACacheService({}, mock_ea)
    service.start()

    assert service.activist_codes_cache[2] == activist_codes[1]
    assert service.changed_entities == set()  # Should not be initialized yet.
    assert service.change_types_cache[
        'resource 1'
    ][1] == resource_to_change_types['resource 1'][0]
    assert service.changed_entities == {
        'resource 1', 'resource 2', 'resource 3'
    }
    assert service.entity_fields_cache[
        'resource 2'
    ]['FIELD 3'] == resource_to_fields['resource 2'][1]
