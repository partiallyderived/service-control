from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Generic, TypeVar

from enough import Sentinel


IndexKey = TypeVar('IndexKey')
IndexValue = TypeVar('IndexValue')
SliceKey = TypeVar('SliceKey')
SliceValue = TypeVar('SliceValue')


class SeqKeyTranslator(Generic[IndexKey, SliceKey]):
    def index_key(self, idx: int) -> IndexKey:
        return idx

    def slice_key(self, slc: slice) -> SliceKey:
        return slc

    def __call__(self, idx_or_slc: int | slice) -> IndexKey | SliceKey:
        match idx_or_slc:
            case int():
                return self.index_key(idx_or_slc)
            case slice():
                return self.slice_key(idx_or_slc)
            case _:
                raise TypeError()


class SeqIndexFn:
    #: Sentinel object indicating an index is "before the beginning."
    BEFORE: Final[Sentinel] = Sentinel()

    #: Sentinel object indicating an index is "after the end."
    AFTER: Final[Sentinel] = Sentinel()

    def neg_in(self, idx: int, length: int) -> int:
        return idx + length

    def neg_oob(self, idx: int, length: int) -> int | Sentinel:
        return self.BEFORE

    def pos_in(self, idx: int, length: int) -> int:
        return idx

    def pos_oob(self, idx: int, length: int) -> int | Sentinel:
        return self.AFTER

    def __call__(self, idx: int, length: int) -> int | Sentinel:
        if idx < -length:
            return self.neg_oob(idx, length)
        if idx < 0:
            return self.neg_in(idx, length)
        if idx < length:
            return self.pos_in(idx, length)
        return self.pos_oob(idx, length)


default_seq_index_fn: Final[SeqIndexFn] = SeqIndexFn()


class PosUnboundedSeqIndexFn(SeqIndexFn):
    def pos_oob(self, idx: int, length: int) -> int:
        return idx


class SliceToRangeAttrFn(ABC):
    @abstractmethod
    def default(self, slc: slice, length: int) -> int:
        ...

    @abstractmethod
    def value(self, raw: int, slc: slice, length: int) -> int:
        ...

    def __call__(self, raw: int | None, slc: slice, length: int) -> int:
        return self.value(raw, slc, length) if raw is not None else self.default(slc, length)


class DirectionToRangeAttrFn(SliceToRangeAttrFn):
    @abstractmethod
    def dir_default(self, length: int, reverse: bool) -> int:
        ...

    def dir_value(self, raw: int, length: int, reverse: bool) -> int:
        match idx := default_seq_index_fn(raw, length):
            case int():
                return idx
            case SeqIndexFn.BEFORE:
                return -reverse
            case SeqIndexFn.AFTER:
                return length - reverse
            case _:
                raise AssertionError()

    def default(self, slc: slice, length: int) -> int:
        return self.dir_default(length, self.is_reversed(slc, length))

    def value(self, raw: int, slc: slice, length: int) -> int:
        return self.dir_value(raw, length, self.is_reversed(slc, length))

    def is_reversed(self, slc: slice, length: int) -> bool:
        return (slc.step or 1) > 0


class DefaultStartAttrFn(DirectionToRangeAttrFn):
    def dir_default(self, length: int, reverse: bool) -> int:
        return 0 if not reverse else length - 1


class DefaultStopAttrFn(DirectionToRangeAttrFn):
    def dir_default(self, length: int, reverse: bool) -> int:
        return length if reverse else -1


class DefaultStepAttrFn(SliceToRangeAttrFn):
    def default(self, slc: slice, length: int) -> int:
        return 1

    def value(self, raw: int, slc: slice, length: int) -> int:
        return raw


class SliceToRange:
    def start(self, slc: slice, length: int) -> int:
        return default_start_attr_fn(slc.start, slc, length)

    def stop(self, slc: slice, length: int) -> int:
        return default_stop_attr_fn(slc.stop, slc, length)

    def step(self, slc: slice, length: int) -> int:
        return default_step_attr_fn(slc.step, slc, length)

    def __call__(self, slc: slice, length: int) -> range:
        return range(self.start(slc, length), self.stop(slc, length), self.step(slc, length))


class SliceToIncreasingRange(SliceToRange):
    def __call__(self, slc: slice, length: int) -> range:
        range_obj = super().__call__(slc, length)
        if range_obj.step < 0:
            return range_obj[::-1]
        return range_obj


default_start_attr_fn: Final[DefaultStartAttrFn] = DefaultStartAttrFn()
default_stop_attr_fn: Final[DefaultStopAttrFn] = DefaultStopAttrFn()
default_step_attr_fn: Final[DefaultStepAttrFn] = DefaultStepAttrFn()
default_slice_to_range: Final[SliceToRange] = SliceToRange()


@dataclass
class BYOCSliceToRange(SliceToRange):
    #: Function to call to calculate the "start" attribute for range. The first argument is the slice value for that
    #: attribute, i.e., :code:`slice.start`, which is None when it is missing.
    start_fn: Callable[[int | None, slice, int], int] = default_start_attr_fn

    #: Function to call to calculate the "stop" attribute for range. The first argument is :code:`slice.stop`.
    stop_fn: Callable[[int | None, slice, int], int] = default_stop_attr_fn

    #: Function to call to calculate the "step" attribute for range. The first argument is :code:`slice.step`.
    step_fn: Callable[[int | None, slice, int], int] = default_step_attr_fn

    def start(self, slc: slice, length: int) -> int:
        return self.start_fn(slc.start, slc, length)

    def stop(self, slc: slice, length: int) -> int:
        return self.stop_fn(slc.stop, slc, length)

    def step(self, slc: slice, length: int) -> int:
        return self.step_fn(slc.step, slc, length)





