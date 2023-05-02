from abc import abstractmethod
from collections.abc import MutableSet

from enough import K

from fspersistentdict.keyedcachedcollection import KeyedCachedCollection


class CachedSet(KeyedCachedCollection[K], MutableSet[K]):
    @abstractmethod
    def _add(self, key: K) -> bool:
        ...

    @abstractmethod
    def _discard(self, key: K) -> bool:
        ...

    def add(self, key: K) -> None:
        if key not in self._present_cache:
            if self._add(key) and self._length >= 0:
                self._length += 1
            self._present_cache.add(key)
            self._absent_cache.discard(key)

    def discard(self, key: K) -> None:
        if key not in self._absent_cache:
            if self._discard(key) and self._length >= 0:
                self._length -= 1
            self._present_cache.discard(key)
            self._absent_cache.add(key)
