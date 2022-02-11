from abc import ABC, abstractmethod
from collections.abc import Iterator, Collection, Mapping, MutableMapping, MutableSequence, MutableSet, Sequence, Set
from typing import Generic, TypeVar

import enough as br
from enough import K, KM1, KM2, T, TP, VP, VP1, VP2


CollType = TypeVar('CollType', bound=Collection)
MapType = TypeVar('MapType', bound=Mapping)
MutMapType = TypeVar('MutMapType', bound=MutableMapping)
MutSeqType = TypeVar('MutSeqType', bound=MutableSequence)
MutSetType = TypeVar('MutSetType', bound=MutableSet)
SeqType = TypeVar('SeqType', bound=Sequence)
SetType = TypeVar('SetType', bound=Set)

class WrappedCollection(Collection[TP], Generic[TP, CollType]):
    # The wrapped collection.
    _wrapped: CollType

    def __init__(self, coll: CollType) -> None:
       self._wrapped = coll

    def __contains__(self, item: TP):
        return item in self._wrapped

    def __iter__(self) -> Iterator[TP]:
        return iter(self._wrapped)

    def __len__(self) -> int:
        return len(self._wrapped)


class WrappedMap(Mapping[K, VP], WrappedCollection[K, MapType]):
    def __getitem__(self, key: K) -> VP:
        return self._wrapped[key]


class Cache(ABC, Generic[KM1, KM2, VP1, VP2]):
    # The underlying cache.
    _cache: dict[KM1, VP1]

    @abstractmethod
    def _get(self, key: KM1) -> VP1:
        ...

    def __init__(self) -> None:
        self._cache = {}

    def __getitem__(self, key: KM2) -> VP2:
        if key in self._cache:
            return self._cache[key]
        return self._cache.setdefault(key, self._get(key))

    def invalidate(self, key: KM1) -> None:
        self._cache.pop(key, None)


class CachedCollection(Collection[TP], Cache[KM1, KM2, VP1, VP2], Generic[TP, KM1, KM2, VP1, VP2, CollType]):
    # The underlying collection.
    _cached: CollType

    def _get(self, key: T) -> VP:
        return self._cached[key]

    @abstractmethod
    def _key_iter(self) -> Iterator[KM1]:
        ...

    def __init__(self, coll_to_cache: CollType) -> None:
        super().__init__()
        self._cached = coll_to_cache

    def __iter__(self) -> Iterator[T]:
        for key in self._key_iter():
            yield self[key]

    def __len__(self) -> int:
        return len(self._cached)


class CachedMap(CachedCollection[T, T, T, VP, VP, Mapping[T, VP]]):
    def _key_iter(self) -> Iterator[T]:
        return iter(self._cached)


class CachedSeq(Sequence[VP], Cache[VP, int, int | slice, VP, VP | list[VP], Sequence[VP]]):
    def _key_iter(self) -> Iterator[int]:
        return iter(range(len(self)))

    def __getitem__(self, item: int | slice) -> VP | list[VP]:
        if isinstance(item, int):
            return super().__getitem__(item)
        elif isinstance(item, slice):
        else:
            raise TypeError()


