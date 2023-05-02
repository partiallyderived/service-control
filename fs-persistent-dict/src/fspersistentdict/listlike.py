from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable, Iterator, MutableSequence
from typing import Generic

from enough import T

import fspersistentdict.util as util


class ListLike(Generic[T], MutableSequence[T]):
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

    def __setitem__(
        self, idx_or_slc: int | slice, value: T | Iterable[T]
    ) -> None:
        match idx_or_slc:
            case int():
                self.set_idx(self._real_idx(idx_or_slc), value)
            case slice():
                if not isinstance(value, Iterable):
                    raise TypeError('can only assign an iterable')
                rng = range(*idx_or_slc.indices(len(self)))
                if rng.step != 1:
                    values = util.ensure_collection(value)
                    if len(rng) != len(values):
                        raise ValueError(
                            f'attempt to assign sequence of size {len(values)} '
                            f'to extended slice of size {len(rng)}'
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
        return TypeError(
            f'{type(self).__name__} indices must be integers or slices, not '
            f'{type(obj).__name__}'
        )

    def insert(self, idx: int, value: T) -> None:
        self.__setitem__(slice(idx, idx), value)

    # noinspection PyMethodMayBeStatic
    def not_int_error(self, obj: object) -> TypeError:
        return TypeError(
            f"'{type(obj).__name__}' object cannot be interpreted as an "
            f"integer"
        )

    def pop(self, idx: int = -1) -> T:
        if not isinstance(idx, int):
            raise self.not_int_error(idx)
        idx = self._real_idx(idx)
        result = self.get_idx(idx)
        self.del_idx(idx)
        return result

    def set_other(self, obj: object, values: T | Iterable[T]) -> None:
        raise self.idx_type_error(obj)

    def set_range(self, rng: range, values: Iterator[T]) -> int:
        i = 0
        for i, (j, value) in enumerate(zip(rng, values), 1):
            self.set_idx(j, value)
        return i
