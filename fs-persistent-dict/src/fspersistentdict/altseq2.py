from __future__ import annotations

from abc import abstractmethod
from collections.abc import Collection, Iterable, Iterator, MutableSequence
from typing import Generic

from enough import T

class MutableSeq(MutableSequence[T], Generic[T]):
    @staticmethod
    def _ensure_collection(items: Iterable[T]) -> Collection[T]:
        return items if isinstance(items, Collection) else list(items)

    @classmethod
    def _empty(cls) -> MutableSequence[T]:
        return cls()

    @abstractmethod
    def _get(self, idx: int) -> T:
        ...

    @abstractmethod
    def _grow(self, n: int) -> None:
        ...

    @abstractmethod
    def _set(self, idx: int, item: T) -> None:
        ...

    @abstractmethod
    def _truncate(self, n: int) -> None:
        ...

    def _del(self, idx: int) -> None:
        self._shift_down(idx + 1, len(self), 1)
        self._truncate(1)

    def _del_cont(self, start: int, stop: int) -> None:
        n = stop - start
        self._shift_down(stop, len(self), n)
        self._truncate(n)

    def _del_range(self, idxs: range) -> None:
        if idxs.step == -1:
            self._del_cont(idxs[-1], idxs[0])
            return
        n = len(idxs)
        for i, j in enumerate(idxs, 1):
            stop = len(self) if i == n else j + idxs.step
            self._shift_down(j + 1, stop, i)
        self._truncate(n)

    def _slice_to_range_del(self, slc: slice) -> range:
        ...

    def _get_cont(self, start: int, stop: int) -> MutableSequence[T]:
        return self._get_range(range(start, stop))

    def _get_range(self, idxs: range) -> MutableSequence[T]:
        seq = self._empty()
        for i in idxs:
            seq.append(self._get(i))
        return seq

    def _get_slice_to_range(self, slc: slice) -> range:
        ...

    def _index(self, idx: int) -> int:
        n = len(self)
        if idx < -n or idx >= n:
            raise self._index_error(idx)
        if idx < 0:
            return idx + n
        return idx

    def _index_error(self, idx: int) -> IndexError:
        return IndexError(f'{type(self).__name__} index out of range')

    def _insert(self, idx: int, items: Iterable[T]) -> None:
        items = self._ensure_collection(items)
        if not items:
            return
        n = len(items)
        self._grow(n)
        self._shift_up(idx, len(self), n)
        self._set_cont_iter(idx, idx + n, iter(items))

    def _insert_stepped(self, start: int, step: int, items: Iterable[T]) -> None:
        items = self._ensure_collection(items)
        if not items:
            return
        n = len(items) * abs(step)
        self._grow(n)
        idxs = range(start, start + n, step)
        if step > 0:
            self._shift_up_insert(idxs)
        else:
            if step == -1:
                self._shift_up(start, len(self), n)
            else:
                self._shift_up_insert(idxs[::-1])
        self._set_range_iter(idxs, iter(items))

    def _map_del_idx(self, idx: int) -> int:
        ...

    def _map_get_index(self, idx: int) -> int:
        ...

    def _map_set_index(self, idx: int, value: T) -> int:
        ...

    def _move(self, src: int, dest: int) -> None:
        self._set(dest, self._get(src))

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
        it = iter(items)
        num_set = self._set_range_iter(idxs, it)
        if num_set < len(idxs):
            if idxs.step < 0:
                self._del_range(idxs[num_set::-1])
            else:
                self._del_range(idxs[num_set:])
        else:
            self._insert_stepped(idxs[-1] + idxs.step, idxs.step, it)

    def _set_range_iter(self, idxs: range, it: Iterator[T]) -> int:
        i = 0
        for i, (j, item) in enumerate(zip(idxs, it), 1):
            self._set(j, item)
        return i

    def _set_slice_to_range(self, slc: slice, values: Iterable[T]) -> range:
        ...

    def _shift_down(self, start: int, stop: int, by: int) -> None:
        for i in range(start, stop):
            self._move(i, i - by)

    def _shift_down_del(self, idxs: range) -> None:
        for i, j in enumerate(idxs, 1):
            self._shift_down(j + 1, j + idxs.step, i)

    def _shift_up(self, start: int, stop: int, by: int) -> None:
        for i in reversed(range(start, stop)):
            self._move(i, i + by)

    def _shift_up_insert(self, idxs: range) -> None:
        n = len(idxs)
        for i, j in enumerate(idxs[::-1], 1):
            self._shift_up(j - idxs.step + 1, j, n - i)

    def _type_error(self, idx_arg: object) -> TypeError:
        return TypeError(f'{type(self).__name__} indices must be integers or slices, not {type(idx_arg).__name__}')

    def __iadd__(self, items: Iterable[T]) -> MutableSeq[T]:
        self.extend(items)
        return self

    def __delitem__(self, idx_or_slc: int | slice) -> None:
        match idx_or_slc:
            case int():
                self._del(self._map_del_idx(idx_or_slc))
            case slice():
                idxs = self._slice_to_range_del(idx_or_slc)
                if id
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
        self._grow(1)
        self._set(len(self) - 1, item)

    def extend(self, items: Iterable[T]) -> None:
        for item in items:
            self.append(item)

    def insert(self, idx: int, item: T) -> None:
        self._insert(idx, [item])
