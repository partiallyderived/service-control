from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Final

from enough import T


def ascending(slc: slice) -> bool:
    return (slc.step or 1) > 0


def default_start(slc: slice, length: int) -> int:
    return 0 if ascending(slc) else length - 1


def default_stop(slc: slice, length: int) -> int:
    return length if ascending(slc) else -1


def range_index(slc_idx: int, slc: slice, length: int) -> int:
    if ascending(slc):
        return lr_index_fn(slc_idx, length)
    return rl_index_fn(slc_idx, length)


def range_start(slc: slice, length: int) -> int:
    return range_index(slc.start, slc, length)


def range_stop(slc: slice, length: int) -> int:
    return range_index(slc.stop, slc, length)


def index_fn(
    left_oob: Callable[[int, int], T] = lambda _, length: -1,
    left_in: Callable[[int, int], T] = lambda idx, length: idx + length,
    right_in: Callable[[int, int], T] = lambda idx, _: idx,
    right_oob: Callable[[int, int], T] = lambda _, length: length
) -> Callable[[int, int], T]:
    def fn(idx: int, length: int) -> T:
        if idx < -length:
            return left_oob(idx, length)
        if idx < 0:
            return left_in(idx, length)
        if idx < length:
            return right_in(idx, length)
        return right_oob(idx, length)
    return fn


def slice_to_range_fn(
    start_default: Callable[[slice, T], int] = default_start,
    start: Callable[[slice, T], int] = range_start,
    stop_default: Callable[[slice, T], int] = default_stop,
    stop: Callable[[slice, T], int] = range_stop,
    step_default: Callable[[slice, T], int] = lambda _1, _2: 1,
    step: Callable[[slice, T], int] = lambda slc, _: slc.step
) -> Callable[[slice, T], range]:
    def fn(slc: slice, arg: T) -> range:
        return range(
            start(slc, arg) if slc.start is not None else start_default(slc, arg),
            stop(slc, arg) if slc.stop is not None else stop_default(slc, arg),
            step(slc, arg) if slc.step is not None else step_default(slc, arg)
        )
    return fn


def inverse_range(range_obj: range) -> Iterator[tuple[int, int]]:
    for i, j in enumerate(range_obj):
        for k in range(j + 1, j + range_obj.step):
            yield i, k


default_index_fn: Final[Callable[[int, int], int]] = index_fn()
lr_index_fn: Final[Callable[[int, int], int]] = index_fn(left_oob=lambda _1, _2: 0)
rl_index_fn: Final[Callable[[int, int], int]] = index_fn(right_oob=lambda _, length: length - 1)
