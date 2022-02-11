from collections.abc import Iterable, Mapping, Set

from enough import T1, T2

from fspersistentdict.impl2 import DirectoryCollection, DirectoryMap, DirectorySeq, DirectorySet, RealType, UserType
from fspersistentdict.sync import SynchronizedCollections, SynchronizedMaps, SynchronizedSeqs, SynchronizedSets


def _item(item: UserType) -> RealType:
    if isinstance(item, Iterable):
        if isinstance(item, Mapping):
            return ...
        if isinstance(item, Set):
            return ...
        # Default to list.
        return ...
    return item


class FSPersistentCollection:
    pass


class FSPersistentDict(SynchronizedMaps[T1, T2]):
    def __setitem__(self, key: T1, value: T2) -> None:
        super().__setitem__(key, _item(value))

