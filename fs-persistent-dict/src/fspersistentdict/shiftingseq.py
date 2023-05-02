from abc import abstractmethod
from collections.abc import Iterator

from enough import T

import fspersistentdict.util as util
from fspersistentdict.listlike import ListLike


class ShiftingSeq(ListLike[T]):
    @abstractmethod
    def _grow(self, n: int) -> None:
        ...

    @abstractmethod
    def _truncate(self, n: int) -> None:
        ...

    def del_idx(self, idx: int) -> None:
        self.shift_down(idx + 1, len(self), 1)

    def del_range(self, rng: range) -> None:
        if rng.step < 0:
            rng = rng[::-1]
        if rng.step > 1:
            self.shift_down_blocks(rng)
        self.shift_down(rng.start + rng.step * len(rng), len(self), len(rng))
        self._truncate(len(rng))

    def insert_many(self, at: int, values: Iterator[T]) -> None:
        values = util.ensure_collection(values)
        n = len(values)
        self._grow(n)
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
