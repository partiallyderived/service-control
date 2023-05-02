from abc import abstractmethod
from collections.abc import Iterator

from fspersistentdict.cachedcollection import CachedCollection

from enough import K


class KeyedCachedCollection(CachedCollection[K]):
    _length: int
    _present_cache: set[K]
    _absent_cache: set[K]

    @abstractmethod
    def _contains(self, obj: K) -> bool:
        ...

    @abstractmethod
    def _iter(self) -> Iterator[K]:
        ...

    def __init__(self) -> None:
        self._length = -1
        self._present_cache = set()
        self._absent_cache = set()

    def __contains__(self, obj: K) -> bool:
        if obj in self._present_cache:
            return True
        if obj in self._absent_cache:
            return False
        result = self._contains(obj)
        if result:
            self._present_cache.add(obj)
        else:
            self._absent_cache.add(obj)
        return result

    def __iter__(self) -> Iterator[K]:
        for k in self._iter():
            self._present_cache.add(k)
            yield k

    def __len__(self) -> int:
        if self._length < 0:
            self._length = self._len()
        return self._length
