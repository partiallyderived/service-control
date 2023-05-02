from abc import abstractmethod
from collections.abc import MutableMapping

from typing import ClassVar

from enough import Sentinel, K, V

from fspersistentdict.keyedcachedcollection import KeyedCachedCollection


class CachedMapping(KeyedCachedCollection[K], MutableMapping[K, V]):
    _MISSING: ClassVar[Sentinel] = Sentinel()

    _cache: dict[K, V]

    @abstractmethod
    def _del(self, key: K) -> None:
        ...

    @abstractmethod
    def _get(self, key: K) -> V:
        ...

    @abstractmethod
    def _set(self, key: K, value: object) -> tuple[V, bool]:
        ...

    def __init__(self) -> None:
        super().__init__()
        self._cache = {}

    def __delitem__(self, key: K) -> None:
        if key in self._absent_cache:
            raise KeyError(key)
        try:
            self._del(key)
        except KeyError:
            self._absent_cache.add(key)
            raise
        if self._length > 0:
            self._length -= 1
        self._cache.pop(key, None)
        self._present_cache.discard(key)
        self._absent_cache.add(key)

    def __getitem__(self, key: K) -> V:
        if key in self._absent_cache:
            raise KeyError(key)
        if (value := self._cache.get(key, self._MISSING)) is self._MISSING:
            try:
                value = self._get(key)
            except KeyError:
                self._absent_cache.add(key)
                raise
            self._cache[key] = value
            self._present_cache.add(key)
        return value

    def __setitem__(self, key: K, value: V) -> None:
        value, new_key = self._set(key, value)
        if new_key and self._length >= 0:
            self._length += 1
        self._cache[key] = value
        self._present_cache.add(key)
        self._absent_cache.discard(key)
