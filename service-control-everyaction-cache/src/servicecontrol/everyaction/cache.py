from abc import abstractmethod, ABC
from collections.abc import Callable, Iterable
from typing import Final, Generic, Protocol, TypeVar

from enough import JSONType
from everyaction import EAClient
from everyaction.objects import ActivistCode, ChangedEntityField, ChangeType

from servicecontrol.core import Service

K = TypeVar('K', contravariant=True)
V = TypeVar('V', covariant=True)


class CacheProto(Protocol[K, V]):
    """Protocol to use for caches, which differs somewhat from :code:`Mapping`."""
    def __getitem__(self, key: K) -> V:
        ...

    def get(self, key: K) -> V | None:
        ...


class Cache(Generic[K, V], ABC):
    """A cache which retrieves resources when they cannot be found."""

    #: The underlying mapping from cached resource keys to resources.
    resources: dict[K, V]

    @abstractmethod
    def _get(self, key: K) -> V | None:
        # Actually get the resource, but don't update self.resources.
        ...

    def __init__(self) -> None:
        """Initializes this cache by initializing a mapping from keys to resources."""
        self.resources = {}

    def __getitem__(self, key: K) -> V:
        """Gets a resource from this cache with the given key.

        :param key: The key to get the resource with.
        :return: The resulting resource.
        :raise KeyError: If no value for :code:`key` could be found even after refreshing.
        """
        value = self.get(key)
        if value is None:
            raise KeyError(value)
        return value

    def get(self, key: K) -> V | None:
        """Gets the resources associated with the given key and updates the cached value for that key.

        :param key: The key to get the resource for.
        :return: The resulting resource, or :code:`None` if no resource could be found for :code:`key` even after
            refreshing.
        """
        resource = self.resources.get(key)
        if resource is None:
            resource = self._get(key)
            if resource is not None:
                self.resources[key] = resource
        return resource


# noinspection PyAbstractClass
class CaseInsensitiveCache(Cache[K, V]):
    """A cache which has case-insensitive keys when they are strings. Implementations are responsible for making sure
    that only lowercase string keys are put into :code:`self.resources`.
    """
    def __getitem__(self, key: K) -> V:
        if isinstance(key, str):
            key = key.lower()
        return super().__getitem__(key)


class ListCache(Cache[K, V]):
    """A cache which uses a given function to list all of a certain kind of resource."""

    _list_fn: Callable[[], Iterable[V]]

    def _get(self, key: K) -> V | None:
        # Just use refresh to get the resources again to get the key.
        self.refresh()
        return self.resources.get(key)

    @abstractmethod
    def _keys(self, resource: V) -> Iterable[K]:
        # A useful abstraction in the case of EveryAction, where resources could have either a name, an ID, or both, and
        # we want to cache each case.
        ...

    def __init__(self, list_fn: Callable[[], Iterable[V]]) -> None:
        """Initializes a ListCache using the given callable to list each resource.

        :param list_fn: The callable returning a collection of every resource.
        """
        super().__init__()
        self._list_fn = list_fn

    def refresh(self) -> None:
        """Refreshes this cache by reloading the list of all its resources. Automatically called when a resource could
        not be found.
        """
        self.resources.clear()
        for resource in self._list_fn():
            for key in self._keys(resource):
                self.resources[key] = resource


# noinspection PyAbstractClass
class CaseInsensitiveListCache(ListCache[K, V], CaseInsensitiveCache[K, V]):
    """A :class:`.ListCache` which is case-insensitive."""


class NameListCache(CaseInsensitiveListCache[str, V]):
    """Cache which uses a given function to list all of a certain kind of resource and maintains a mapping from
    case-insensitive resource names to the resource.
    """

    def _keys(self, resource: V) -> list[str]:
        return [resource.name.lower()]


class IDNameListCache(CaseInsensitiveListCache[int | str, V]):
    """Cache which uses a given function to list all of a certain kind of resource and maintains both a mapping from
    the resource int IDs to the resource and the resource string names to the resource.
    """

    def _keys(self, resource: V) -> list[int | str]:
        return [resource.name.lower(), resource.id]


class ResourceNameListCaches(CaseInsensitiveCache[str, ListCache[K, V]]):
    """A collection of caches for different resources which have similar ways of listing all 'sub-resources' (i.e.,
    change types for a changed entity resource) by passing the name of the top-level resource to a function.
    """

    _valid_resource_fn: Callable[[str], bool]
    _cache_factory: Callable[[str], ListCache[K, V]]

    def _get(self, resource: str) -> ListCache[K, V] | None:
        # First check if resource is a valid resource.
        if not self._valid_resource_fn(resource):
            return None

        # See if we already have the cache. If we do, refresh it. Otherwise, create it.
        cache = self.resources.get(resource)
        if cache is not None:
            cache.refresh()
        else:
            cache = self._cache_factory(resource)
            self.resources[resource.lower()] = cache
        return cache

    def __init__(
        self,
        valid_resource_fn: Callable[[str], bool],
        cache_factory: Callable[[str], ListCache[K, V]]
    ) -> None:
        """Initializes this cache by using the given function to list all sub-resources using the name of the resource.

        :param valid_resource_fn: The function to use to determine whether a particular top-level resource is valid.
        :param cache_factory: The function to use to create list caches from a string.
        """
        super().__init__()
        self._valid_resource_fn = valid_resource_fn
        self._cache_factory = cache_factory


class EACacheService(Service):
    """A service which caches some EveryAction resources for quick retrieval."""

    EXPORTS: Final[frozenset[str]] = frozenset(
        {'activist_codes_cache', 'change_types_cache', 'entity_fields_cache'}
    )
    NAME: Final[str] = 'everyaction-cache'
    SCHEMA: Final[JSONType] = {
        'description': 'EveryAction cache service configuration.',
        'type': 'object',
        'properties': {
            # No configurations right now.
        },
        'additionalProperties': False
    }

    # The EveryAction client used to populate caches.
    _ea: EAClient

    #: Cached ActivistCodes.
    activist_codes_cache: IDNameListCache[ActivistCode] | None

    #: Set of changed entity names.
    changed_entities: set[str] | None

    #: Cached ChangeTypes for each changed entity resource.
    change_types_cache: ResourceNameListCaches[int | str, ChangeType] | None

    #: Cached ChangedEntityFields for each kind of changed entity.
    entity_fields_cache: ResourceNameListCaches[str, ChangedEntityField] | None

    def _is_valid_entity(self, name: str) -> bool:
        # Detects whether the given name is a valid entity for changed entity export jobs.
        if name.lower() in self.changed_entities:
            return True
        self.changed_entities = set(r.lower() for r in self._ea.changed_entities.resources())
        return name.lower() in self.changed_entities

    def __init__(self, config: JSONType, ea: EAClient) -> None:
        """Initializes this service by creating exported attributes.

        :param config: The config to use for this service. Currently unused.
        :param ea: The EveryAction client to use to maintain this cache.
        """
        super().__init__(config)
        self.activist_codes_cache = None
        self.changed_entities = set()
        self.change_types_cache = None
        self._ea = ea
        self.entity_fields_cache = None

    def start(self) -> None:
        """Starts this service by creating each cache."""
        # noinspection PyTypeChecker
        self.activist_codes_cache = IDNameListCache(lambda: self._ea.activist_codes.list(limit=0))
        self.change_types_cache = ResourceNameListCaches(
            self._is_valid_entity,
            lambda r: IDNameListCache(lambda: self._ea.changed_entities.change_types(r))
        )
        self.entity_fields_cache = ResourceNameListCaches(
            self._is_valid_entity,
            lambda r: NameListCache(lambda: self._ea.changed_entities.fields(r))
        )
