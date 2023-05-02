from collections.abc import Collection, Iterable

from enough.types import T


def ensure_collection(values: Iterable[T]) -> Collection[T]:
    return values if isinstance(values, Collection) else list(values)
