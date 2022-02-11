from abc import ABC, abstractmethod
from typing import Generic

from bobbeyreese import T, T1, T2
from collections.abc import Iterable, MutableSequence


class NormalMutableSequence(ABC, MutableSequence[T], Generic[T]):
    @staticmethod
    def _check_index(idx: int, length: int) -> None:
        if idx >= length or idx < -length:
            raise IndexError(idx)

    @staticmethod
    def _slice_to_range(slc: slice, length: int) -> range:


    def __delitem__(self, idx_or_slc: int | slice) -> None:
        if isinstance(idx_or_slc, int):
            self.delete(idx_or_slc)
            return


    @abstractmethod
    def append(self, item: T) -> None:
        ...

    def clear(self) -> None:
        for i in range(len(self)):
            self.pop()

    @abstractmethod
    def delete(self, idx: int) -> None:
        ...

    def delete_cont(self, start: int, end: int) -> None:
        for i in range(end, start, -1):
            self.delete(i)

    @abstractmethod
    def delete_step(self, start: int, end: int, step: int) -> None:
        for i in range(end, start, -step):
            self.delete(i)

    def extend(self, items: Iterable[T]) -> None:
        for item in items:
            self.append(item)

    @abstractmethod
    def insert(self, idx: int, item: T) -> None:
        ...

    @abstractmethod
    def insert_cont(self, idx: int, items: Iterable[T]) -> None:
        ...

    def pop(self, idx: int = -1) -> T:
        length = len(self)
        self._check_index(idx, length)
        idx %= length
        result = self[idx]
        self.delete(idx)
        return result

    @abstractmethod
    def set(self, idx: int, item: T) -> None:
        ...

    @abstractmethod
    def set_cont(self, start: int, end: int, items: Iterable[T]) -> None:


    @abstractmethod
    def set_step(self, idx: int, num: int, step: int, items: Iterable[T]) -> None:
        ...
