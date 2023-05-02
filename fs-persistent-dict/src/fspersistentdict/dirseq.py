from collections.abc import Collection, Iterable, Iterator, Sequence

from enough.types import T, T1, T2

from fspersistentdict.cachedshiftingseq import CachedShiftingSeq
from fspersistentdict.dircoll import DirectoryCollection


class DirectorySeq(DirectoryCollection[T], CachedShiftingSeq[T]):
    """A mutable sequence whose contents are persisted to and synchronized with
    the disc.
    """

    def _do_grow(self, n: int) -> None:
        # No need: _do_set_idx will make the file.
        pass

    def _do_truncate(self, n: int) -> None:
        for i in range(len(self) - n, len(self)):
            self._delete(self._idx_path(i))

    def _do_set_idx(
        self, idx: int, value: T1 | Collection[T2]
    ) -> T1 | DirectoryCollection[T2]:
        # Set an index by saving the object to disc. Sequences, Mappings, and
        # Sets will be converted to DirectoryCollections, so propagate that
        # change via the return value.
        return self._save(value, self._idx_path(idx))

    def _get_missing(self, idx: int) -> T:
        # Get a missing index by loading the object from disc.
        return self._load(self._idx_path(idx))

    def _idx_path(self, idx: int) -> str:
        return self._abs(str(idx))

    def __init__(self, path: str, initial: Sequence[T] | None = None) -> None:
        """Init by loading the sequence saved at ``path``, if it exists and is a
        directory, or else creating a directory if it does not exist.

        :param path: Path to load or create sequence from.
        :param initial: Initial contents to use. When this parameter is omitted,
            it is assumed that a directory sequence already exists here.
            Therefore, explicitly specify an empty collection if the intent is
            to initialize a new, empty directory seq.
        :raise FileExistsError: If ``initial`` is specified and ``path`` exists.
        :raise FileNotFoundError: If either of the following are true:
            * ``initial`` is specified but the parent directory of ``path`` does
              not exist.
            * ``initial`` is unspecified and ``path`` does not exist.
        :raise NotADirectoryError: If ``initial`` is unspecified and ``path``
            exists but is not a directory.
        """
        CachedShiftingSeq.__init__(self)
        DirectoryCollection.__init__(self, path, initial is not None)
        if initial:
            for (i, e) in enumerate(initial):
                self.set_idx(i, e)

    def __delitem__(self, key: int | slice) -> None:
        self._require_valid()
        super().__delitem__(key)

    def __getitem__(self, key: int | slice) -> T | list[T]:
        self._require_valid()
        return super().__getitem__(key)

    def __setitem__(self, key: int | slice, value: T | Iterable[T]) -> None:
        self._require_valid()
        super().__setitem__(key, value)

    def __iter__(self) -> Iterator[T]:
        self._require_valid()
        return super().__iter__()

    def __len__(self) -> int:
        self._require_valid()
        return super().__len__()

    def move(self, from_idx: int, to_idx: int) -> None:
        self._cache.move(from_idx, to_idx)
        self._move(self._idx_path(from_idx), self._idx_path(to_idx))
