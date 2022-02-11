import contextlib
import typing
from abc import ABC, abstractmethod
from collections.abc import (
    Collection, Iterator, Iterable, Mapping, MutableMapping, MutableSequence, MutableSet, Sequence, Set, ValuesView
)
from typing import Final, Generic, TypeVar

import enough as br
from enough import K, KM1, KM2, Sentinel, T, TP, V, VP, VP1, VP2
from sparse_list import SparseList

CollType = TypeVar('CollType', bound=Collection)
MapType = TypeVar('MapType', bound=Mapping)
MutMapType = TypeVar('MutMapType', bound=MutableMapping)
MutSeqType = TypeVar('MutSeqType', bound=MutableSequence)
MutSetType = TypeVar('MutSetType', bound=MutableSet)
SeqType = TypeVar('SeqType', bound=Sequence)
SetType = TypeVar('SetType', bound=Set)

_SENTINEL: Final[Sentinel] = Sentinel()


class Wrapped(Generic[TP]):
    # The wrapped object.
    _wrapped: TP

    def __init__(self, obj: TP) -> None:
        self._wrapped = obj

    def __eq__(self, other: object) -> bool:
        return self._wrapped == other

    def __hash__(self) -> int:
        return hash(self._wrapped)

    def __ne__(self, other: object) -> bool:
        return self._wrapped != other

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._wrapped!r})'

    def __str__(self) -> str:
        return str(self._wrapped)


class WrappedCollection(Collection[TP], Wrapped[CollType]):
    def __contains__(self, item: TP):
        return item in self._wrapped

    def __iter__(self) -> Iterator[TP]:
        return iter(self._wrapped)

    def __len__(self) -> int:
        return len(self._wrapped)


class WrappedMap(Mapping[K, VP], WrappedCollection[K, MapType]):
    def __getitem__(self, key: K) -> VP:
        return self._wrapped[key]


class WrappedMutableMap(MutableMapping[K, V], WrappedMap[K, V, MutMapType]):
    def __delitem__(self, key: K) -> None:
        del self._wrapped[key]

    def __setitem__(self, key: K, value: V) -> None:
        self._wrapped[key] = value


class WrappedSeq(Sequence[VP], WrappedCollection[VP, SeqType]):
    def __getitem__(self, idx_or_slc: int | slice) -> VP:
        return self._wrapped[idx_or_slc]


class WrappedMutableSeq(MutableSequence[T], WrappedSeq[V, MutSeqType]):
    def __delitem__(self, idx_or_slc: int | slice) -> None:
        del self._wrapped[idx_or_slc]

    def __setitem__(self, idx_or_slc: int | slice, value: T | Iterable[T]) -> None:
        self._wrapped[idx_or_slc] = value

    def insert(self, index: int, value: T) -> None:
        self._wrapped.insert(index, value)


class WrappedSet(Set[VP], WrappedCollection[VP, SetType]):
    pass


class WrappedMutableSet(MutableSet[T], WrappedSet[T, MutSetType]):
    def add(self, value: T) -> None:
        self._wrapped.add(value)

    def discard(self, value: T) -> None:
        self._wrapped.discard(value)


class CachedCollection(WrappedCollection[TP, CollType]):
    # The cached length.
    _len: int | None

    def __init__(self, coll: CollType) -> None:
        super().__init__(coll)
        self._len = None

    def __len__(self) -> int:
        if self._len is None:
            return len(self._wrapped)
        return self._len

    def invalidate(self) -> None:
        self._len = None


class CachedMap(WrappedMap[K, VP, MapType], CachedCollection[K, MapType]):
    # Cached items for the wrapped map.
    _cache: dict[K, VP | Sentinel]

    # Cache of keys known to not be in the wrapped map.
    _missing: set[K]

    def __init__(self, mapping: MapType) -> None:
        super().__init__(mapping)
        self._cache = {}
        self._missing = set()

    def __contains__(self, key: K) -> bool:
        if key in self._cache:
            return True
        if key in self._missing:
            return False
        result = super().__contains__(key)
        if result:
            self._cache[key] = _SENTINEL
        else:
            self._missing.add(key)

    def __getitem__(self, key: K) -> VP:
        if (value := self._cache.get(key, _SENTINEL)) is _SENTINEL:
            if value in self._missing:
                raise KeyError(value)
            try:
                return self._cache.setdefault(key, super().__getitem__(key))
            except KeyError:
                self._missing.add(value)
                raise KeyError(value)
        return value

    def __iter__(self) -> Iterator[K]:
        if len(self._cache) == self._len:
            return iter(self._cache)
        return super().__iter__()

    def invalidate(self) -> None:
        super().invalidate()
        self._cache.clear()
        self._missing.clear()


class CachedMutableMap(WrappedMutableMap[K, V, MutMapType], CachedMap[K, V, MutMapType]):
    def __delitem__(self, key: K) -> None:
        if key in self._missing:
            raise KeyError(key)
        try:
            super().__delitem__(key)
        except KeyError:
            self._missing.add(key)
            raise KeyError(key)
        self._cache.pop(key, None)
        if self._len is not None:
            self._len -= 1
        self._missing.add(key)

    def __setitem__(self, key: K, value: V) -> None:
        is_new = self._len is not None and key not in self
        super().__setitem__(key, value)
        self._cache[key] = value
        self._missing.discard(key)
        if is_new:
            self._len += 1


class CachedSeq(WrappedSeq[TP, SeqType], CachedCollection[TP, SeqType]):
    # Initial size to use for cache.
    _INITIAL_SIZE: Final[int] = 11

    # Cached items for the wrapped sequence.
    _cache: SparseList

    def _ensure_cache_size(self, size: int) -> None:
        self._cache.size = max(self._cache.size, size)

    def _idxs(self, idx_or_slc: int | slice) -> range:
        try:
            return range(len(self))[idx_or_slc]
        except IndexError:
            raise IndexError(f'Sequence index out of range') from None
        except TypeError:
            raise TypeError(
                f'Sequence indices must be integers or slices, not {type(idx_or_slc).__name__}'
            ) from None

    def __init__(self, sequence: SeqType) -> None:
        super().__init__(sequence)
        self._cache = SparseList(self._INITIAL_SIZE, default_value=_SENTINEL)

    def __getitem__(self, idx_or_slc: int | slice) -> TP | list[TP]:
        if isinstance(idx_or_slc, int) and idx_or_slc >= 0:
            # Try to avoid calculating len if possible.
            self._ensure_cache_size(idx_or_slc)
            if (item := self._cache[idx_or_slc]) is _SENTINEL:
                item = super().__getitem__(idx_or_slc)
                self._cache[idx_or_slc] = item
            return item
        items = [self[i] for i in self._idxs(idx_or_slc)]
        if isinstance(idx_or_slc, int):
            return items[0]
        return items

    def __iter__(self) -> Iterator[TP]:
        return map(self.__getitem__, range(len(self)))

    def __len__(self) -> int:
        if self._len is not None:
            return self._len
        length = super().__len__()
        self._ensure_cache_size(length)
        return length

    def invalidate(self) -> None:
        super().invalidate()
        self._cache.elements.clear()


class CachedMutableSeq(WrappedMutableSeq[T, MutSeqType], CachedSeq[T, MutSeqType]):
    def _insert(self, idx: int, items: Iterable[T]) -> None:
        if not isinstance(items, Collection):
            items = list(items)
        slc = slice(idx, idx)
        super().__setitem__(slc, items)
        self._cache.__setitem__(slc, items)
        if self._len is not None:
            self._len += len(items)

    def __delitem__(self, idx_or_slc: int | slice) -> None:
        super().__delitem__(idx_or_slc)
        with contextlib.suppress(IndexError):
            del self._cache[idx_or_slc]
        if self._len is not None:
            # Note that _len is still set to the old length, so we'll get actual indices.
            self._len -= len(self._idxs(idx_or_slc))

    def __setitem__(self, idx_or_slc: int | slice, item: T | Iterable[T]) -> None:
        if isinstance(idx_or_slc, int):
            super().__setitem__(idx_or_slc, item)
            if idx_or_slc < 0:
                if idx_or_slc >= -len(self):
                    idx_or_slc += len(self)
                else:
                    raise IndexError('Sequence index out of range')
            self._ensure_cache_size(idx_or_slc)
            self._cache[idx_or_slc] = item
            return
        items = typing.cast(item, Iterable[T])
        idxs = self._idxs(idx_or_slc)
        if not idxs:
            self._insert(idxs.start, items)
            return
        self._ensure_cache_size(max(idxs[0], idxs[-1]))
        if idxs.step != 1:
            # When step is not 1, we cannot use an iterator over items since assigning an extended slice to an iterable
            # of a length different than the number of indices covered by that slice is not allowed. Therefore, we need
            # to convert items to a Collection if necessary to get the length and prevent erroneous mutations before the
            # end of iteration. While we're at it, we may as well defer to __setitem__ for _cache and _wrapped since we
            # no longer have to worry about the iterator being consumed.
            if not isinstance(items, Collection):
                items = list(items)
            super().__setitem__(idx_or_slc, items)
            self._cache[idx_or_slc] = items
            return
        n = 0
        items_iter = iter(items)
        for n, (i, itm) in enumerate(zip(idxs, items_iter), 1):
            super().__setitem__(i, itm)
            self._cache[i] = itm
        if n < len(idxs):
            # Less items than indices, delete the elements at the remaining indices.
            idxs = idxs[n:]
            del self[slice(idxs.start, idxs.stop, idxs.step)]
        else:
            # More items than indices, insert the remaining items after the last index (note that step == 1).
            self._insert(idxs[-1] + 1, items_iter)


class CachedSet(WrappedSet[TP, SetType], CachedCollection[TP, SetType]):
    # Cache of objects which are in the wrapped set.
    _present: set[TP]

    # Cache of objects which are not in the wrapped set.
    _missing: set[TP]

    def __init__(self, st: SetType) -> None:
        super().__init__(st)
        self._present = set()
        self._missing = set()

    def __contains__(self, item: TP) -> bool:
        if item in self._present:
            return True
        if item in self._missing:
            return False
        result = super().__contains__(item)
        if result:
            self._present.add(item)
        else:
            self._missing.add(item)

    def __iter__(self) -> Iterable[TP]:
        if self._len == len(self._present):
            return iter(self._present)
        return super().__iter__()

    def invalidate(self) -> None:
        super().invalidate()
        self._present.clear()
        self._missing.clear()


class CachedMutableSet(WrappedMutableSet[T, MutSetType], CachedSet[T, MutSeqType]):
    def add(self, value: T) -> None:
        if self._len is not None and value not in self:
            self._len += 1
        super().add(value)
        self._present.add(value)
        self._missing.discard(value)

    def discard(self, value: T) -> None:
        if self._len is not None and value in self:
            self._len -= 1
        super().discard(value)
        self._present.discard(value)
        self._missing.add(value)


