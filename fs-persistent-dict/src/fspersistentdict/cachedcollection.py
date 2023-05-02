from abc import abstractmethod
from collections.abc import Collection
from typing import Generic

from enough import T


class CachedCollection(Generic[T], Collection[T]):
    @abstractmethod
    def _len(self) -> int:
        ...
