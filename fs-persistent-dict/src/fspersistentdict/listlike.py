from __future__ import annotations

from abc import abstractmethod
from collections.abc import Collection, Iterable, Iterator, MutableSequence

from enough import Sentinel, T


def ensure_collection(values: Iterable[T]) -> Collection[T]:
    return values if isinstance(values, Collection) else list(values)


class ListLike(MutableSequence[T]):
    @classmethod
    def empty(cls) -> ListLike[T]:
        return cls()

    def __delitem__(self, idx_or_slc: int | slice) -> None:
        match idx_or_slc:
            case int():
                self.del_idx(self._real_idx(idx_or_slc))
            case slice():
                self.del_range(range(*idx_or_slc.indices(len(self))))
            case _:
                self.del_other(idx_or_slc)

    def __getitem__(self, idx_or_slc: int | slice) -> T | Iterable[T]:
        match idx_or_slc:
            case int():
                return self.get_idx(self._real_idx(idx_or_slc))
            case slice():
                return self.get_range(range(*idx_or_slc.indices(len(self))))
            case _:
                return self.get_other(idx_or_slc)

    def __setitem__(self, idx_or_slc: int | slice, value: T | Iterable[T]) -> None:
        match idx_or_slc:
            case int():
                self.set_idx(self._real_idx(idx_or_slc), value)
            case slice():
                if not isinstance(value, Iterable):
                    raise TypeError('can only assign an iterable')
                rng = range(*idx_or_slc.indices(len(self)))
                if rng.step != 1:
                    values = ensure_collection(value)
                    if len(rng) != len(values):
                        raise ValueError(
                            f'attempt to assign sequence of size {len(values)} to extended slice of size {len(rng)}'
                        )
                    self.set_range(rng, iter(values))
                else:
                    it = iter(value)
                    num_set = self.set_range(rng, it)
                    if num_set < len(rng):
                        self.del_range(rng[num_set:])
                    else:
                        self.insert_many(rng.start + num_set, it)
            case _:
                self.set_other(idx_or_slc, value)

    def _real_idx(self, idx: int) -> int:
        length = len(self)
        if idx >= length:
            raise self.idx_error(idx)
        if idx >= 0:
            return idx
        if idx >= -length:
            return idx + length
        raise self.idx_error(idx)

    @abstractmethod
    def del_idx(self, idx: int) -> None:
        ...

    @abstractmethod
    def get_idx(self, idx: int) -> T:
        ...

    @abstractmethod
    def insert_many(self, at: int, values: Iterator[T]) -> None:
        ...

    @abstractmethod
    def set_idx(self, idx: int, value: T) -> None:
        ...

    def del_other(self, obj: object) -> None:
        raise self.idx_type_error(obj)

    def del_range(self, rng: range) -> None:
        if rng.step < 0:
            rng = rng[::-1]
        for i in rng:
            self.del_idx(i)

    def get_other(self, obj: object) -> T:
        raise self.idx_type_error(obj)

    def get_range(self, rng: range) -> MutableSequence[T]:
        result = self.empty()
        for i in rng:
            result.append(self.get_idx(i))
        return result

    # noinspection PyUnusedLocal
    def idx_error(self, idx: int) -> IndexError:
        return IndexError(f'{type(self)} index out of range')

    def idx_type_error(self, obj: object) -> TypeError:
        return TypeError(f'{type(self).__name__} indices must be integers or slices, not {type(obj).__name__}')

    def insert(self, idx: int, value: T) -> None:
        self.set_range(range(idx, idx), value)

    # noinspection PyMethodMayBeStatic
    def not_int_error(self, obj: object) -> TypeError:
        return TypeError(f"'{type(obj).__name__}' object cannot be interpreted as an integer")

    def pop(self, idx: int = -1) -> T:
        if not isinstance(idx, int):
            raise self.not_int_error(idx)
        idx = self._real_idx(idx)
        result = self.get_idx(idx)
        self.del_idx(idx)
        return result

    def set_range(self, rng: range, values: Iterator[T]) -> int:
        i = 0
        for i, (j, value) in enumerate(zip(rng, values), 1):
            self.set_idx(j, value)
        return i

    def set_other(self, obj: object, values: T | Iterable[T]) -> None:
        raise self.idx_type_error(obj)


class ShiftingSeq(ListLike[T]):
    @abstractmethod
    def grow(self, n: int) -> None:
        ...

    @abstractmethod
    def truncate(self, n: int) -> None:
        ...

    def del_idx(self, idx: int) -> None:
        self.shift_down(idx + 1, len(self), 1)

    def del_range(self, rng: range) -> None:
        if rng.step < 0:
            rng = rng[::-1]
        if rng.step > 1:
            self.shift_down_blocks(rng)
        self.shift_down(rng.start + rng.step * len(rng), len(self), len(rng))
        self.truncate(len(rng))

    def insert_many(self, at: int, values: Iterator[T]) -> None:
        values = ensure_collection(values)
        n = len(values)
        self.grow(n)
        self.shift_up(at, len(self), n)
        for i, val in enumerate(values, at):
            self.set_idx(i, val)

    def move(self, src: int, dest: int) -> None:
        self.set_idx(dest, self.get_idx(src))

    def shift_down(self, start: int, stop: int, n: int) -> None:
        for i in range(start, stop):
            self.move(i, i - n)

    def shift_down_blocks(self, rng: range) -> None:
        for i, j in enumerate(rng, 1):
            self.shift_down(j + 1, j + rng.step, i)

    def shift_up(self, start: int, stop: int, n: int) -> None:
        for i in reversed(range(start, stop)):
            self.move(i, i + n)


class SparseSeq(ShiftingSeq[T]):
    #: The value which is used by default in place of missing values.
    DEFAULT_MISSING: Sentinel = Sentinel()

    # Variable which keeps track of the length of the SparseSeq.
    _len: int

    #: Underlying dictionary which keeps track of the explicitly set indices.
    dct: dict[int, T]

    #: Value to use for missing elements.
    missing: object

    def __init__(self, values: Iterable[T] = (), missing: object = DEFAULT_MISSING) -> None:
        self._len = 0
        self.dct = {}
        self.missing = missing
        self.extend(values)

    def get_idx(self, idx: int) -> object:
        return self.dct.get(idx, self.missing)

    def grow(self, n: int) -> None:
        self._len += n

    def resize(self, new_size: int) -> None:
        if new_size < len(self):
            self.del_range(range(new_size, len(self)))
        self._len = new_size

    def set_idx(self, idx: int, value: T) -> None:
        if value == self.missing:
            self.dct.pop(idx, None)
        else:
            self.dct[idx] = value

    def truncate(self, n: int) -> None:
        self._len -= n
