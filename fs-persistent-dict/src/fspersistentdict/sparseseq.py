from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from enough import Sentinel, T

from fspersistentdict.shiftingseq import ShiftingSeq


class SparseSeq(ShiftingSeq[T]):
    #: The value which is used by default in place of missing values.
    MISSING: ClassVar[Sentinel] = Sentinel()

    # Variable which keeps track of the length of the SparseSeq.
    _len: int

    #: Underlying dictionary which keeps track of the explicitly set indices.
    dct: dict[int, T]

    #: Value to use for missing elements.
    missing: object

    def _grow(self, n: int) -> None:
        self._len += n

    def _truncate(self, n: int) -> None:
        self._len -= n

    def __init__(
        self, values: Iterable[T] = (), missing: object = MISSING
    ) -> None:
        self._len = 0
        self.dct = {}
        self.missing = missing
        self.extend(values)

    def __len__(self) -> int:
        return self._len

    def get_idx(self, idx: int) -> object:
        return self.dct.get(idx, self.missing)

    def resize(self, new_size: int) -> None:
        if new_size < len(self):
            self.del_range(range(new_size, len(self)))
        self._len = new_size

    def set_idx(self, idx: int, value: T) -> None:
        if value == self.missing:
            self.dct.pop(idx, None)
        else:
            self.dct[idx] = value
