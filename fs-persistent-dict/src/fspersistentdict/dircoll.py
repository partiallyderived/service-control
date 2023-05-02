from __future__ import annotations

import os
import os.path
import pickle
import shutil
import typing
from abc import abstractmethod
from collections.abc import (
    Collection, Iterator, MutableMapping, MutableSequence, MutableSet
)
from typing import ClassVar, NoReturn, TypeVar

import enough
from enough import EnumErrors, T, T1, T2

from sortedcontainers import SortedDict

from fspersistentdict.cachedcollection import CachedCollection

if typing.TYPE_CHECKING:
    from fspersistentdict.dirmap import DirectoryMap
    from fspersistentdict.dirseq import DirectorySeq
    from fspersistentdict.dirset import DirectorySet
    DirCollection = DirectoryMap | DirectorySeq | DirectorySet
    DC = TypeVar('DC', bound=DirCollection)


class DirectoryCollectionError(Exception):
    pass


class DirectoryCollectionErrors(EnumErrors[DirectoryCollectionError]):
    BadKind = '"{kind}" is not a valid DirectoryCollection kind', 'kind'
    InvalidDirectoryCollection = (
        'This directory collection has been invalidated.'
    )


class DirectoryCollection(CachedCollection[T]):
    """A collection whose contents are saved to disc upon mutation."""

    _KIND_FILE: ClassVar[str] = '.kind'
    _kind_to_type: ClassVar[dict[str, type[DC]]]
    _path_to_coll: ClassVar[SortedDict[str, DirCollection]]

    # Root of the directory collection.
    _path: str

    @staticmethod
    def _child_iter(
        path: str
    ) -> Iterator[tuple[str, DirCollection]]:
        path_dict = DirectoryCollection._path_to_coll
        try:
            i = path_dict.index(path)
        except ValueError:
            return
        items = path_dict.items()
        path = os.path.join(path, '')
        while i < len(path_dict) and items[i][0].startswith(path):
            yield items[i]
            i += 1

    @staticmethod
    def _delete(path: str) -> None:
        if os.path.isfile(path):
            os.remove(path)
            return
        for p, _ in list(DirectoryCollection._child_iter(path)):
            del DirectoryCollection._path_to_coll[p]
            shutil.rmtree(p)

    @staticmethod
    def _load(path: str) -> T:
        # Use pickle to load the value stored at path.
        if os.path.isdir(path):
            return DirectoryCollection._load_dir_coll(path)
        with open(path) as f:
            return pickle.load(f)

    @staticmethod
    def _load_dir_coll(path: str) -> DirCollection:
        # Load the directory collection at the given path.
        if (existing := DirectoryCollection._path_to_coll) is not None:
            return existing
        return DirectoryCollection._load_type(path)(path)

    @staticmethod
    def _load_type(path: str) -> type[DC]:
        # Load the directory collection type from the given directory.
        kind_path = os.path.join(path, DirectoryCollection._KIND_FILE)
        if not os.path.isfile(kind_path):
            raise FileNotFoundError(
                f'kind path {kind_path} either does not exist, or is not a '
                f'file.'
            )
        with open(kind_path) as f:
            kind = f.read()
            if (typ := DirectoryCollection._kind_to_type.get(kind)) is None:
                raise DirectoryCollectionErrors.BadKind(kind)
            return typ

    @staticmethod
    def _move(from_path: str, to_path: str) -> None:
        # Move an object from from_path to to_path.
        if os.path.exists(to_path):
            DirectoryCollection._delete(to_path)
        for p, dir_coll in list(DirectoryCollection._child_iter(from_path)):
            dir_coll._path = p.replace(from_path, to_path, 1)
            del DirectoryCollection._path_to_coll[p]
            DirectoryCollection._path_to_coll[dir_coll._path] = dir_coll
        os.rename(from_path, to_path)

    @staticmethod
    def _obj_paths(path: str) -> list[str]:
        # Get the list of paths to files corresponding to saved objects.
        return [
            os.path.abspath(p) for p in os.listdir(path)
            if not p.startswith('.')
        ]


    @staticmethod
    def _save(
        value: T1 | Collection[T2], path: str
    ) -> T1 | DirectoryCollection[T2]:
        # Dump the given value into the given file-like object.
        enough.rm(path, recursive=True, force=True)

        match value:
            case MutableSequence():
                from fspersistentdict.dirseq import DirectorySeq
                return DirectorySeq(path, value)
            case MutableSet():
                from fspersistentdict.dirset import DirectorySet
                return DirectorySet(path, value)
            case MutableMapping():
                from fspersistentdict.dirmap import DirectoryMap
                return DirectoryMap(path, value)
            case _:
                with open(path, 'w') as f:
                    pickle.dump(value, f)
                return value

    @classmethod
    @abstractmethod
    def kind(cls) -> str:
        """
        :return: The "kind" of this directory collection
            ("seq", "set", or "map").
        """
        ...

    def _abs(self, path: str) -> str:
        # Get the absolute path relative to this collection's root, or just the
        # given path if it is already absolute.
        if not os.path.isabs(path):
            return os.path.join(self._path, path)
        return path

    def _len(self) -> int:
        return sum(not p.startswith('.') for p in os.listdir(self._path))

    def _require_valid(self) -> None:
        if not self.valid:
            raise DirectoryCollectionErrors.InvalidDirectoryCollection()

    def __init__(self, path: str, new: bool) -> None:
        # Init a directory collection by writing its kind to disc and checking
        # if the given path if appropriate according to whether a new collection
        # is being created or not.
        path = os.path.abspath(path)
        self._path = path
        if new:
            os.mkdir(path)
            with open(self._abs('.kind')) as f:
                f.write(self.kind())
        elif not os.path.isdir(path):
            if os.path.exists(path):
                raise NotADirectoryError(path)
            raise FileNotFoundError(path)
        self._path_to_coll[path] = self

    def __hash__(self) -> NoReturn:
        raise TypeError(f'unhashable type: {type(self).__name__}')

    @property
    def path(self) -> str:
        """
        :return: The path at which this directory collection is rooted.
        """
        return self._path

    @property
    def valid(self) -> bool:
        """
        :return: ``True`` if this is a valid directory collection, ``False``
            otherwise.
        """
        return self._path in self._path_to_coll

    def invalidate(self) -> None:
        """Mark this directory collection as no longer being valid. Useful, for
        example, for when the corresponding directory has been modified outside
        of the usage of :class:`.DirectoryCollection` and its subclasses.
        """
        if self._path_to_coll.get(self.path) is self:
            del self._path_to_coll[self.path]
