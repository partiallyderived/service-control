from abc import abstractmethod

from enough import T

from fspersistentdict.cachedcollection import CachedCollection
from fspersistentdict.shiftingseq import ShiftingSeq
from fspersistentdict.sparseseq import SparseSeq


class CachedShiftingSeq(CachedCollection[T], ShiftingSeq[T]):
    """A :class:`.ShiftingSeq` whose values are cached using a
    :class:`.SparseSeq` to prevent costly retrievals for cached values.
    """
    # SparseSeq to use as a cache.
    _cache: SparseSeq[T]

    @classmethod
    def empty(cls) -> list[T]:
        return []

    @abstractmethod
    def _do_grow(self, n: int) -> None:
        # Perform the grow operation.
        ...

    @abstractmethod
    def _do_set_idx(self, idx: int, value: object) -> T:
        ...

    @abstractmethod
    def _do_truncate(self, n: int) -> None:
        ...

    @abstractmethod
    def _get_missing(self, idx: int) -> T:
        ...

    def _grow(self, n: int) -> None:
        self._do_grow(n)
        self._cache._grow(n)

    def _truncate(self, n: int) -> None:
        self._do_truncate(n)
        self._cache._truncate(n)

    def __init__(self) -> None:
        """Init this cached shifting seq."""
        self._cache = SparseSeq()
        self._cache._grow(self._len())

    def __len__(self) -> int:
        return len(self._cache)

    def get_idx(self, idx: int) -> T:
        if (value := self._cache.get_idx(idx)) is not SparseSeq.MISSING:
            return value
        value = self._get_missing(idx)
        self._cache.set_idx(idx, value)
        return value

    def set_idx(self, idx: int, value: T) -> None:
        value = self._do_set_idx(idx, value)
        self._cache.set_idx(idx, value)
