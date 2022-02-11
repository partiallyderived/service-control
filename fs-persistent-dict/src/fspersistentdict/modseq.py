from __future__ import annotations
from abc import abstractmethod
from collections.abc import Collection, Iterable, Iterator, MutableSequence

from enough import Sentinel, T


def ensure_collection(values: Iterable[T]) -> Collection[T]:
    return values if isinstance(values, Collection) else list(values)


class MutableSeq(MutableSequence[T]):
    def __delitem__(self, idx_or_slc: int | slice) -> None:
        match idx_or_slc:
            case int():
                self.del_int(idx_or_slc)
            case slice():
                self.del_slc(idx_or_slc)
            case _:
                self.del_other(idx_or_slc)

    def __getitem__(self, idx_or_slc: int | slice) -> T | Iterable[T]:
        match idx_or_slc:
            case int():
                return self.get_int(idx_or_slc)
            case slice():
                return self.get_slc(idx_or_slc)
            case _:
                return self.get_other(idx_or_slc)

    def __setitem__(self, idx_or_slc: int | slice, value: T | Iterable[T]) -> None:
        match idx_or_slc:
            case int():
                self.set_int(idx_or_slc, value)
            case slice():
                self.set_slc(idx_or_slc, value)
            case _:
                self.set_other(idx_or_slc, value)

    @abstractmethod
    def del_int(self, idx: int) -> None:
        ...

    @abstractmethod
    def del_slc(self, slc: slice) -> None:
        ...

    @abstractmethod
    def get_int(self, idx: int) -> T:
        ...

    @abstractmethod
    def get_slc(self, slc: slice) -> MutableSequence[T]:
        ...

    def pop(self, idx: int = -1) -> T:
        if not isinstance(idx, int):
            raise self.not_int_error(idx)
        result = self.get_int(idx)
        self.del_int(idx)
        return result

    @abstractmethod
    def set_int(self, idx: int, value: T) -> None:
        ...

    @abstractmethod
    def set_slc(self, slc: slice, values: Iterable[T]) -> None:
        ...

    def del_other(self, obj: object) -> None:
        raise self.key_type_error(obj)

    def get_other(self, obj: object) -> T:
        raise self.key_type_error(obj)

    def idx_error(self, idx: int) -> IndexError:
        return IndexError(f'{type(self)} index out of range')

    def insert(self, idx: int, value: T) -> None:
        self.set_slc(slice(idx, idx), value)

    def key_type_error(self, obj: object) -> TypeError:
        return TypeError(f'{type(self).__name__} indices must be integers or slices, not {type(obj).__name__}')

    def not_int_error(self, obj: object) -> TypeError:
        return TypeError(f"'{type(obj).__name__}' object cannot be interpreted as an integer")

    def set_other(self, obj: object, values: T | Iterable[T]) -> None:
        raise self.key_type_error(obj)


class IndexRangeSeq(MutableSeq[T]):
    @abstractmethod
    def del_idx(self, idx: int) -> None:
        ...

    @abstractmethod
    def del_range(self, rng: range) -> None:
        ...

    @abstractmethod
    def get_idx(self, idx: int) -> None:
        ...

    @abstractmethod
    def get_range(self, rng: range) -> MutableSequence[T]:
        ...

    @abstractmethod
    def set_idx(self, idx: int, value: T) -> None:
        ...

    @abstractmethod
    def set_range(self, rng: range, values: Iterable[T]) -> None:
        ...

    def __contains__(self, value: T) -> bool:
        for i in range(len(self)):
            if self.get_idx(i) == value:
                return True
        return False

    def __iter__(self) -> Iterator[T]:
        for i in range(len(self)):
            yield self.get_idx(i)

    def __reversed__(self) -> Iterator[T]:
        for i in range(len(self) - 1, -1, -1):
            yield self.get_idx(i)

    def count(self, value: T) -> int:
        return sum(self.get_idx(i) == value for i in range(len(self)))

    def del_int(self, idx: int) -> None:
        self.del_idx(self.idx_del(idx))

    def del_slc(self, slc: slice) -> None:
        self.del_range(self.slc_to_range_del(slc))

    def get_int(self, idx: int) -> T:
        return self.get_idx(self.idx_get(idx))

    def get_slc(self, slc: slice) -> MutableSequence[T]:
        return self.get_range(self.slc_to_range_get(slc))

    def idx_default(self, idx: int) -> int:
        length = len(self)
        if idx < -length:
            raise self.idx_error(idx)
        if idx < 0:
            return idx + length
        if idx < length:
            return idx
        raise self.idx_error(idx)

    def idx_del(self, idx: int) -> int:
        return self.idx_default(idx)

    def idx_get(self, idx: int) -> int:
        return self.idx_default(idx)

    def idx_set(self, idx: int, value: T) -> int:
        return self.idx_default(idx)

    def index(self, value: T, start: int = 0, stop: int = -1) -> int:
        for i in self.slc_to_range_get(slice(start, stop)):
            if self.get_idx(i) == value:
                return i
        raise ValueError(f'{value} is not in {type(self).__name__}')

    def remove(self, value: T) -> None:
        self.del_idx(self.index(value))

    def set_int(self, idx: int, value: T) -> None:
        self.set_idx(self.idx_set(idx, value), value)

    def set_slc(self, slc: slice, values: Iterable[T]) -> None:
        self.set_range(self.slc_to_range_set(slc, values), values)

    def slc_to_range_default(self, slc: slice) -> range:
        return range(*slc.indices(len(self)))

    def slc_to_range_del(self, slc: slice) -> range:
        return self.slc_to_range_default(slc)

    def slc_to_range_get(self, slc: slice) -> range:
        return self.slc_to_range_default(slc)

    def slc_to_range_set(self, slc: slice, values: Iterable[T]) -> range:
        return self.slc_to_range_default(slc)


class CaseHookIndexRangeSeq(IndexRangeSeq[T]):
    @classmethod
    def empty(cls) -> MutableSequence[T]:
        return cls()

    @abstractmethod
    def insert_cont(self, at: int, values: Iterable[T]) -> None:
        ...

    def check_set_range(self, rng: range, values: Iterable[T]) -> None:
        if rng.step != 1:
            values = ensure_collection(values)
            if len(rng) != len(values):
                raise ValueError(
                    f'attempt to assign sequence of size {len(values)} to extended slice of size {len(rng)}'
                )

    def del_cont(self, rng: range) -> None:
        self.del_cont_reversed(rng[::-1])

    def del_cont_reversed(self, rng: range) -> None:
        for i in rng:
            self.del_idx(i)

    def del_range(self, rng: range) -> None:
        match rng.step > 0, abs(rng.step) == 1:
            case True, True:
                self.del_cont(rng)
            case True, False:
                self.del_stepped(rng)
            case False, True:
                self.del_cont_reversed(rng)
            case False, False:
                self.del_stepped_reversed(rng)

    def del_stepped(self, rng: range) -> None:
        self.del_stepped_reversed(rng[::-1])

    def del_stepped_reversed(self, rng: range) -> None:
        for i in rng:
            self.del_idx(i)

    def get_cont(self, rng: range) -> MutableSequence[T]:
        return self.get_range_default(rng)

    def get_cont_reversed(self, rng: range) -> MutableSequence[T]:
        return self.get_range_default(rng)

    def get_range(self, rng: range) -> None:
        match rng.step > 0, abs(rng.step) == 1:
            case True, True:
                self.get_cont(rng)
            case True, False:
                self.get_stepped(rng)
            case False, True:
                self.get_cont_reversed(rng)
            case False, False:
                self.get_stepped_reversed(rng)

    def get_range_default(self, rng: range) -> MutableSequence[T]:
        values = self.empty()
        for i in rng:
            values.append(self.get_idx(i))
        return values

    def get_stepped(self, rng: range) -> MutableSequence[T]:
        return self.get_range_default(rng)

    def get_stepped_reversed(self, rng: range) -> Iterable[T]:
        return self.get_range_default(rng)

    def idx_del(self, idx: int) -> int:
        length = len(self)
        if idx < -length:
            return self.idx_neg_oob_del(idx)
        if idx < 0:
            return self.idx_neg_del(idx)
        if idx < length:
            return self.idx_pos_del(idx)
        return self.idx_pos_oob_del(idx)

    def idx_get(self, idx: int) -> int:
        length = len(self)
        if idx < -length:
            return self.idx_neg_oob_get(idx)
        if idx < 0:
            return self.idx_neg_get(idx)
        if idx < length:
            return self.idx_pos_get(idx)
        return self.idx_pos_oob_get(idx)

    def idx_set(self, idx: int, value: T) -> int:
        length = len(self)
        if idx < -length:
            return self.idx_neg_oob_set(idx, value)
        if idx < 0:
            return self.idx_neg_set(idx, value)
        if idx < length:
            return self.idx_pos_set(idx, value)
        return self.idx_pos_oob_set(idx, value)

    def idx_neg_default(self, idx: int) -> int:
        return idx + len(self)

    def idx_neg_del(self, idx: int) -> int:
        return self.idx_neg_default(idx)

    def idx_neg_get(self, idx: int) -> int:
        return self.idx_neg_default(idx)

    def idx_neg_set(self, idx: int, value: T) -> int:
        return self.idx_neg_default(idx)

    def idx_neg_oob_default(self, idx: int) -> int:
        raise self.idx_error(idx)

    def idx_neg_oob_del(self, idx: int) -> int:
        return self.idx_neg_oob_default(idx)

    def idx_neg_oob_get(self, idx: int) -> int:
        return self.idx_neg_oob_default(idx)

    def idx_neg_oob_set(self, idx: int, value: T) -> int:
        return self.idx_neg_oob_default(idx)

    def idx_pos_default(self, idx: int) -> int:
        return idx

    def idx_pos_del(self, idx: int) -> int:
        return self.idx_pos_default(idx)

    def idx_pos_get(self, idx: int) -> int:
        return self.idx_pos_default(idx)

    def idx_pos_set(self, idx: int, value: T) -> int:
        return self.idx_pos_default(idx)

    def idx_pos_oob_default(self, idx: int) -> int:
        raise self.idx_error(idx)

    def idx_pos_oob_del(self, idx: int) -> int:
        return self.idx_pos_oob_default(idx)

    def idx_pos_oob_get(self, idx: int) -> int:
        return self.idx_pos_oob_default(idx)

    def idx_pos_oob_set(self, idx: int, value: T) -> int:
        return self.idx_pos_oob_default(idx)

    def insert(self, idx: int, value: T) -> None:
        if not isinstance(idx, int):
            raise self.not_int_error(idx)
        self.insert_cont(self.idx_set(idx, value), [value])

    def insert_cont_reversed(self, at: int, values: Iterable[T]) -> None:
        if list(values):
            raise NotImplementedError('insert_cont_reversed is not implemented.')

    def insert_stepped(self, at: int, step: int, values: Iterable[T]) -> None:
        if list(values):
            raise NotImplementedError('insert_stepped is not implemented.')

    def insert_stepped_reversed(self, at: int, step: int, values: Iterable[T]) -> None:
        if list(values):
            raise NotImplementedError('insert_stepped_reversed is not implemented.')

    def set_cont(self, rng: range, values: Iterable[T]) -> None:
        it = iter(values)
        n = self.set_range_iter(rng, it)
        if n < len(rng):
            self.del_cont(rng[n:])
        else:
            self.insert_cont(rng.stop, it)

    def set_cont_reversed(self, rng: range, values: Iterable[T]) -> None:
        it = iter(values)
        n = self.set_range_iter(rng, it)
        if n < len(rng):
            self.del_cont_reversed(rng[n:])
        else:
            self.insert_cont_reversed(rng.stop, values)

    def set_range(self, rng: range, values: Iterable[T]) -> None:
        self.check_set_range(rng, values)
        match rng.step > 0, abs(rng.step) == 1:
            case True, True:
                self.set_cont(rng, values)
            case True, False:
                self.set_stepped(rng, values)
            case False, True:
                self.set_cont_reversed(rng, values)
            case False, False:
                self.set_stepped_reversed(rng, values)

    def set_range_iter(self, rng: range, it: Iterator[T]) -> int:
        i = 0
        for i, (j, val) in enumerate(zip(rng, it), 1):
            self.set_idx(j, val)
        return i

    def set_stepped(self, rng: range, values: Iterable[T]) -> None:
        it = iter(values)
        n = self.set_range_iter(rng, it)
        if n < len(rng):
            self.del_stepped(rng[n:])
        else:
            self.insert_stepped(rng.start + len(rng) * rng.step, rng.step, it)

    def set_stepped_reversed(self, rng: range, values: Iterable[T]) -> None:
        it = iter(values)
        n = self.set_range_iter(rng, it)
        if n < len(rng):
            self.del_stepped_reversed(rng[n:])
        else:
            self.insert_stepped_reversed(rng.start + len(rng) * rng.step, rng.step, it)


class ShiftingSeq(CaseHookIndexRangeSeq[T]):
    @abstractmethod
    def grow(self, n: int) -> None:
        ...

    @abstractmethod
    def truncate(self, n: int) -> None:
        ...

    def __iadd__(self, values: Iterable[T]) -> ShiftingSeq[T]:
        self.extend(values)
        return self

    def append(self, value: T) -> None:
        self.grow(1)
        self.set_idx(len(self) - 1, value)

    def del_cont(self, rng: range) -> None:
        self.shift_down(rng.stop, len(self), len(rng))
        self.truncate(len(rng))

    def del_cont_reversed(self, rng: range) -> None:
        self.shift_down(rng.start + 1, len(self), len(rng))
        self.truncate(len(rng))

    def del_idx(self, idx: int) -> None:
        self.shift_down(idx + 1, len(self), 1)
        self.truncate(1)

    def del_stepped(self, rng: range) -> None:
        if not rng:
            return
        self.shift_down_blocks(rng)
        self.shift_down(rng[-1] + 1, len(self), len(rng))

    def del_stepped_reversed(self, rng: range) -> None:
        self.del_stepped(rng[::-1])

    def extend(self, values: Iterable[T]) -> None:
        values = ensure_collection(values)
        n = len(values)
        start = len(self)
        self.grow(n)
        self.set_range_iter(range(start, start + n), iter(values))

    def insert_cont(self, at: int, values: Iterable[T]) -> None:
        values = ensure_collection(values)
        n = len(values)
        self.grow(n)
        self.shift_up(at, len(self) - n, n)
        self.set_range_iter(range(at, at + n), iter(values))

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

    def shift_up_blocks(self, rng: range) -> None:
        for i, j in enumerate(reversed(rng), 1):
            self.shift_up(j - 1, j - rng.step, i)


class SparseSeq(ShiftingSeq[T]):
    # The underlying length.
    _len: int

    #: Default value to use for missing values.
    DEFAULT_MISSING: Sentinel = Sentinel()

    #: The underlying dictionary of indices to values.
    dct: dict[int, T]

    #: Object to use in case of a missing value.
    default: T | Sentinel

    def __init__(self, values: Iterable[T] = (), default: T | Sentinel = DEFAULT_MISSING) -> None:
        self._len = 0
        self.dct = {}
        self.default = default
        self.extend(values)

    def __len__(self) -> int:
        return self._len

    def check_set_range(self, rng: range, values: Iterable[T]) -> None:
        pass

    def grow(self, n: int) -> None:
        self._len += n

    def get_idx(self, idx: int) -> T | Sentinel:
        return self.dct.get(idx, self.default)

    def set_idx(self, idx: int, value: T) -> None:
        self._len = max(self._len, idx)
        self.set_in_bounds(idx, value)

    def set_in_bounds(self, idx: int, value: T) -> None:
        if value != self.default:
            self.dct[idx] = value

    def truncate(self, n: int) -> None:
        self._len -= n
