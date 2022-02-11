from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableSequence
from typing import ClassVar, Final

from enough import Sentinel, T

from altseq import IndexProcessor, MutableSeq


class SparseIndexProcessor(IndexProcessor):
    def in_bounds(self, idx: int, parent: MutableSequence) -> bool:
        return idx >= -len(parent)

    def slice_range(self, slc: slice, parent: MutableSequence) -> range:
        idxs = range(*slc.indices(len(parent)))
        start = slc.start if slc.start and slc.start > idxs.start else idxs.start
        stop = slc.stop if slc.stop and slc.stop > idxs.stop else idxs.stop
        return range(start, stop, idxs.step)


class SparseSeq(MutableSeq[T]):
    # _del_idx_processor: ClassVar[IndexProcessor] = ...
    _get_idx_processor: ClassVar[IndexProcessor] = SparseIndexProcessor()
    _set_idx_processor: ClassVar[IndexProcessor] = SparseIndexProcessor()

    # The default value to use for keys.
    _default: T | Sentinel

    # Underlying length of this collection.
    _len: int

    # The default default value to use for keys. Using a sentinel allows None to be used by default.
    UNSET: Final[Sentinel] = Sentinel()

    #: Underlying dictionary containing the set keys.
    dct: dict[int, T]

    def _default_slc_start(self, pos_step: bool) -> int:
        return 0 if pos_step else len(self) - 1

    def _default_slc_stop(self, pos_step: bool) -> int:
        return len(self) if pos_step else -1

    def _ensure_len(self, at_least: int) -> None:
        self._len = max(at_least, self._len)

    def _add_space(self, n: int) -> None:
        self._len += n

    def _del(self, idx: int) -> None:
        self._del_cont(idx, idx + 1)

    def _del_cont(self, start: int, stop: int) -> None:
        self._del_range(range(start, stop, 1))

    def _del_range(self, idxs: range) -> None:
        # Deletes the given range of indices in O(len(self)) time. This implementation takes advantage of the fact that,
        # given an index, we can count the number of elements that occur before it in the given range, whereas if we had
        # to delete multiple arbitrary indices that do not necessarily fit into a range, we might have to do some
        # sorting. In the general case, radix sort could be used to delete arbitrary indices in linear time provided the
        # integer indices are bounded, perhaps less than 2**64, for example.

        # We don't actually iterate over this range, it just makes calculations easier.
        n = len(idxs)
        new_len = self._len - n
        last = idxs[-1]
        idxs_to_del = set()
        items_to_set = {}
        num_dense_to_shift = self._len - (idxs[-1] + 1) + (idxs.step - 1) * n
        if num_dense_to_shift <= self.population:
            # We are deleting elements close enough to the end that it is more efficient to iterate over the "dense"
            # trailing indices rather than all sparse indices.
            super()._del_range(idxs)
            return
        for i, val in self.dct.items():
            if i >= idxs.start:
                idxs_to_del.add(i)
                # If i < start, the item stays where it is.
                # Otherwise, we need to delete it (since we're only iterating over populated indices, there's no
                # guarantee it will not need to be deleted in lieu of being replaced by another moved item).
                if i > last:
                    # All indices past the last deleted index must be shifted down by the full length of the range.
                    items_to_set[i - n] = val
                elif i % idxs.step != idxs.start % idxs.step:
                    # When i % step == start % step and i <= last, i is in the range of indices we need to delete and we
                    # should ignore it.
                    # Otherwise, we need to calculate the amount by which to shift down the item at index i.
                    # This is the same as the number of range indices that appear before it.
                    # Since i > start, we know we need to shift down by at least 1.
                    # Then, (i - start) // step gives the number of additional "steps" in the range before i.
                    # This means the amount we should shift down by is (i - start) // step + 1.
                    shift_by = (i - idxs.start) // idxs.step + 1
                    items_to_set[i - shift_by] = val
        for i in idxs_to_del:
            del self.dct[i]
        self.dct.update(items_to_set)
        self._len = new_len

    def _get(self, idx: int) -> T | Sentinel:
        return self.dct.get(idx, self._default)

    def _get_cont(self, start: int, stop: int) -> SparseSeq[T]:
        return self._get_range(range(start, stop, 1))

    def _get_range(self, idxs: range) -> SparseSeq[T]:
        result = SparseSeq(default=self.default)
        result._len = len(idxs)
        if idxs.step > 0:
            if idxs.start >= self._len:
                return result
            num_dense = min(len(idxs), 1 + (self._len - 1 - idxs.start) // idxs.step)
        else:
            num_dense = len(idxs)
        if num_dense <= self._len:
            for i in range(num_dense):
                result._set(i, self._get(idxs[i]))
        else:
            for i, val in self.dct.items():
                if idxs.start <= i < idxs.stop and not (i - idxs.start) % idxs.step:
                    result.dct[i - idxs.start] = val
        return result

    def _move(self, src: int, dest: int) -> None:
        # Avoid length check.
        if (value := self.dct.get(src, self._default)) != self._default:
            self.dct[dest] = value
            del self.dct[src]
        else:
            self.dct.pop(dest, None)

    def _set(self, idx: int, value: T) -> None:
        self._ensure_len(idx)
        if value == self._default:
            self.dct.pop(idx, None)
        else:
            self.dct[idx] = value

    def _set_cont(self, start: int, stop: int, values: Iterable[T]) -> None:
        self._set_range(range(start, stop), values)

    def _set_range(self, idxs: range, values: Iterable[T]) -> None:
        if not idxs:
            return
        # For a SparseSeq, it is more efficient to delete and insert elements before setting new values, since setting
        # values may increase the number of indices we have to shift, if the indices for any of those values was
        # previously unset.
        # In order to insert or delete before setting, we need to know the length of values, so we ensure it is a
        # collection.
        values = self._ensure_collection(values)
        diff = len(values) - len(idxs)

        # Below, value_idxs, which is to be a range over the indices over which ALL values from values will be set, is
        # defined in one of the following blocks.
        if diff < 0:
            # More indices than values, need to delete some items.
            # Note that diff is negative.
            value_idxs = idxs[:-diff]
            del_idxs = idxs[-diff:]
            del self[del_idxs.start:del_idxs.stop:del_idxs.step]
        elif diff > 0:
            num_insertions = diff * idxs.step
            shift_idx = max(idxs[0], idxs[-1]) + 1
            if shift_idx < len(self):
                self._shift_up(shift_idx, self._len, num_insertions)
            if idxs.step < 0:
                value_idxs = range(idxs.start + num_insertions, idxs.stop, idxs.step)
            else:
                value_idxs = range(idxs.start, idxs.stop + num_insertions, idxs.step)
            self._len += num_insertions
        else:
            value_idxs = idxs
        if (
            isinstance(values, SparseSeq)
            and values.default == self.default
            and len(value_idxs) > self.population + values.population
        ):
            idxs_to_del = []
            for i in self.dct:
                if i in value_idxs and (i - value_idxs.start) // value_idxs.step not in values:
                    idxs_to_del.append(i)
            for i in idxs_to_del:
                del self.dct[i]
            for i, val in values.dct.items():
                self.dct[value_idxs[i]] = val
        else:
            self._set_range_iter(value_idxs, iter(values))

    def _shift_down(self, start: int, stop: int, by: int) -> None:
        if stop - start <= self.population:
            super()._shift_down(start, stop, by)
        else:
            self._shift_down_sparse(start, stop, by)

    def _shift_up(self, start: int, stop: int, by: int) -> None:
        if stop - start <= self.population:
            super()._shift_up(start, stop, by)
        else:
            self._shift_up_sparse(start, stop, by)

    def _shift_down_sparse(self, start: int, stop: int, by: int) -> None:
        self.dct = {i - by * (start <= i < stop): val for i, val in self.dct.items()}

    def _shift_up_sparse(self, start: int, stop: int, by: int) -> None:
        self.dct = {i + by * (start <= i < stop): val for i, val in self.dct.items()}

    def _truncate(self, n: int) -> None:
        self._len -= n

    def __iadd__(self, other: Iterable[T]) -> SparseSeq[T]:
        self.extend(other)
        return self

    def __init__(self, values: Iterable[T] = (), default: T | Sentinel = UNSET) -> None:
        self._default = default
        self._len = 0
        self.dct = {}
        self.extend(values)

    def __len__(self) -> int:
        return self._len

    @property
    def default(self) -> T | Sentinel:
        return self._default

    def extend(self, values: Iterable[T]) -> None:
        if isinstance(values, SparseSeq):
            for i, val in values.dct.items():
                self.dct[self._len + i] = val
            self._len += len(values)
        else:
            super().extend(values)

    @property
    def population(self) -> int:
        return len(self.dct)

    def resize(self, size: int) -> None:
        if not isinstance(size, int):
            raise TypeError(f'Cannot interpret {type(size).__name__} object "{size}" as an integer.')
        if size < 0:
            raise ValueError(f'Cannot resize to negative integer {size}.')
        if size < self._len:
            self._del_cont(size, self._len)
        else:
            self._len = size
