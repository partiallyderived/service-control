from __future__ import annotations

from collections.abc import (
    Collection, Iterable, Iterator, Mapping, MutableMapping, MutableSequence, MutableSet, Set, ValuesView
)
from typing import Final, Generic, Protocol

from enough import Sentinel, T, T1, T2


_SENTINEL: Final[Sentinel] = Sentinel()


class ClearableCollection(Protocol[T]):
    def __contains__(self, key: T1) -> bool:
        ...

    def __iter__(self) -> Iterator[T]:
        ...

    def __len__(self) -> int:
        ...

    def clear(self) -> None:
        ...


class SynchronizedCollections(Collection[T], Generic[T]):
    #: The underlying collections.
    collections: list[ClearableCollection[T]]

    def __init__(self, collections: Iterable[ClearableCollection[T]]) -> None:
        self.collections = list(collections)
        if not self.collections:
            raise ValueError('At least one collection must be specified.')

    def __contains__(self, item: T) -> bool:
        return item in self.collections[0]

    def __eq__(self, other: object) -> bool:
        return self.collections[0] == other

    def __iter__(self) -> Iterator[T]:
        return iter(self.collections[0])

    def __len__(self) -> int:
        return len(self.collections[0])

    def __ne__(self, other: object) -> bool:
        return self.collections[0] != other

    def __str__(self) -> str:
        return str(self.collections[0])

    def __repr__(self) -> str:
        return repr(self.collections[0])

    def clear(self) -> None:
        for collection in self.collections:
            collection.clear()


class MutableItemCollection(ClearableCollection[T], Protocol[T, T1, T2]):
    def __delitem__(self, key: T1) -> None:
        ...

    def __getitem__(self, key: T1) -> T2:
        ...

    def __setitem__(self, key: T1, value: T2) -> None:
        ...


class SynchronizedItemCollections(SynchronizedCollections[T], Generic[T, T1, T2]):
    #: The underlying :class:`ItemCollections <.ItemCollection>`.
    collections: list[MutableItemCollection[T, T1, T2]]

    def __delitem__(self, key: T1) -> None:
        for collection in self.collections:
            del collection[key]

    def __getitem__(self, key: T1) -> T2:
        return self.collections[0][key]

    def __setitem__(self, key: T1, value: T2) -> None:
        for collection in self.collections:
            collection[key] = value


class SynchronizedMaps(MutableMapping[T1, T2], SynchronizedCollections[T1, T1, T2]):
    #: The underlying mappings.
    collections: list[MutableMapping[T1, T2]]


class SynchronizedSeqs(MutableSequence[T], SynchronizedItemCollections[T, int | slice, T | Iterable[T]]):
    #: The underlying sequences.
    collections: list[MutableSequence[T]]

    def insert(self, idx: int, value: T) -> None:
        for collection in self.collections:
            collection.insert(idx, value)


class SynchronizedSets(MutableSet[T], SynchronizedCollections[T]):
    #: The underlying sets.
    collections: list[MutableSet[T]]

    def add(self, value: T) -> None:
        for collection in self.collections:
            collection.add(value)

    def discard(self, value: T) -> None:
        for collection in self.collections:
            collection.discard(value)
