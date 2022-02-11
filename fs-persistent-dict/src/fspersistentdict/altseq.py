from __future__ import annotations

from abc import abstractmethod
from collections.abc import Collection, Iterable, Iterator, MutableSequence
from typing import ClassVar, Generic

from enough import T


class IndexProcessor:
    def __call__(self, idx_or_slc: int | slice, parent: MutableSequence) -> int | range | tuple[int, int]:
        match idx_or_slc:
            case int():
                return self.process_int(idx_or_slc, parent)
            case slice():
                return self.process_slice(idx_or_slc, parent)
            case _:
                raise self.type_error(idx_or_slc, parent)

    def in_bounds(self, idx: int, parent: MutableSequence) -> bool:
        length = len(parent)
        return -length <= idx < length

    def index_error(self, idx_or_slc: int | slice, parent: MutableSequence) -> IndexError:
        return IndexError(f'{type(parent).__name__} index out of range')

    def process_int(self, idx: int, parent: MutableSequence) -> int:
        if not self.in_bounds(idx, parent):
            raise self.index_error(idx, parent)
        return self.true_index(idx, parent)

    def process_slice(self, slc: slice, parent: MutableSequence) -> range | tuple[int, int]:
        if not self.slice_in_bounds(slc, parent):
            raise self.index_error(slc, parent)
        idxs = self.slice_range(slc, parent)
        if idxs.step == 1:
            return idxs.start, idxs.stop
        return idxs

    def slice_in_bounds(self, slc: slice, parent: MutableSequence) -> bool:
        return True

    def slice_range(self, slc: slice, parent: MutableSequence) -> range:
        return range(*slc.indices(len(parent)))

    def true_index(self, idx: int, parent: MutableSequence) -> int:
        if idx < 0:
            return idx + len(parent)
        return idx

    # noinspection PyMethodMayBeStatic
    def type_error(self, idx_arg: object, parent: MutableSequence[object]) -> TypeError:
        return TypeError(f'{type(parent).__name__} indices must be integers or slices, not {type(idx_arg).__name__}')


class UnorderedIndexProcessor(IndexProcessor):
    def slice_range(self, slc: slice, parent: MutableSequence[object]) -> range:
        idxs = super().slice_range(slc, parent)
        if idxs.step < 0:
            return idxs[::-1]


class MutableSeq(MutableSequence[T], Generic[T]):
    _del_idx_processor: ClassVar[IndexProcessor] = UnorderedIndexProcessor()
    _get_idx_processor: ClassVar[IndexProcessor] = IndexProcessor()
    _set_idx_processor: ClassVar[IndexProcessor] = IndexProcessor()

    @staticmethod
    def _ensure_collection(items: Iterable[T]) -> Collection[T]:
        return items if isinstance(items, Collection) else list(items)

    @classmethod
    def _empty(cls) -> MutableSequence[T]:
        return cls()

    @abstractmethod
    def _add_space(self, n: int) -> None:
        ...

    def _del(self, idx: int) -> None:
        self._shift_down(idx + 1, len(self), 1)
        self._truncate(1)

    def _del_cont(self, start: int, stop: int) -> None:
        n = stop - start
        self._shift_down(stop, len(self), n)
        self._truncate(n)

    def _del_range(self, idxs: range) -> None:
        n = len(idxs)
        for i, j in enumerate(idxs, 1):
            stop = len(self) if i == n else j + idxs.step
            self._shift_down(j + 1, stop, i)
        self._truncate(n)

    @abstractmethod
    def _get(self, idx: int) -> T:
        ...

    def _get_cont(self, start: int, stop: int) -> MutableSequence[T]:
        return self._get_range(range(start, stop))

    def _get_range(self, idxs: range) -> MutableSequence[T]:
        seq = self._empty()
        for i in idxs:
            seq.append(self._get(i))
        return seq

    def _insert(self, idx: int, items: Iterable[T]) -> None:
        items = self._ensure_collection(items)
        if not items:
            return
        n = len(items)
        self._add_space(n)
        self._shift_up(idx, len(self), n)
        self._set_cont_iter(idx, idx + n, iter(items))

    def _move(self, src: int, dest: int) -> None:
        self._set(dest, self._get(src))

    @abstractmethod
    def _set(self, idx: int, item: T) -> None:
        ...

    def _set_cont(self, start: int, stop: int, items: Iterable[T]) -> None:
        it = iter(items)
        num_set = self._set_cont_iter(start, stop, it)
        if num_set < stop - start:
            self._del_cont(start + num_set, stop)
        else:
            self._insert(stop, it)

    def _set_cont_iter(self, start: int, stop: int, it: Iterator[T]) -> int:
        return self._set_range_iter(range(start, stop), it)

    def _set_range(self, idxs: range, items: Iterable[T]) -> None:
        if not isinstance(items, Collection):
            items = list(items)
        if len(items) != len(idxs):
            raise ValueError(f'attempt to assign sequence of size {len(items)} to extended slice of size {len(idxs)}')
        self._set_range_iter(idxs, iter(items))

    def _set_range_iter(self, idxs: range, it: Iterator[T]) -> int:
        i = 0
        for i, (j, item) in enumerate(zip(idxs, it), 1):
            self._set(j, item)
        return i

    def _shift_down(self, start: int, stop: int, by: int) -> None:
        for i in range(start, stop):
            self._move(i, i - by)

    def _shift_up(self, start: int, stop: int, by: int) -> None:
        for i in reversed(range(start, stop)):
            self._move(i, i + by)

    @abstractmethod
    def _truncate(self, n: int) -> None:
        ...

    def __iadd__(self, items: Iterable[T]) -> MutableSeq[T]:
        self.extend(items)
        return self

    def __delitem__(self, idx_or_slc: int | slice) -> None:
        match (idx_or_range := self._del_idx_processor(idx_or_slc, self)):
            case int():
                self._del(idx_or_range)
            case tuple(start, stop):
                self._del_cont(start, stop)
            case range():
                self._del_range(idx_or_range)
            case _:
                raise AssertionError('Processor should have raised TypeError.')

    def __getitem__(self, idx_or_slc: int | slice) -> T | MutableSequence[T]:
        match (idx_or_range := self._get_idx_processor(idx_or_slc, self)):
            case int():
                return self._get(idx_or_range)
            case tuple(start, stop):
                return self._get_cont(start, stop)
            case range():
                return self._get_range(idx_or_range)
            case _:
                raise AssertionError('Processor should have raised TypeError.')

    def __setitem__(self, idx_or_slc: int | slice, item: T | Iterable[T]) -> None:
        match (idx_or_range := self._set_idx_processor(idx_or_slc, self)):
            case int():
                self._set(idx_or_range, item)
            case tuple(start, stop):
                self._set_cont(start, stop, item)
            case range():
                self._set_range(idx_or_range, item)
            case _:
                raise AssertionError('Processor should have raised TypeError.')

    def append(self, item: T) -> None:
        self._add_space(1)
        self._set(len(self) - 1, item)

    def extend(self, items: Iterable[T]) -> None:
        for item in items:
            self.append(item)

    def insert(self, idx: int, item: T) -> None:
        self._insert(idx, [item])
