import os
import os.path
from abc import abstractmethod
from collections.abc import Iterator
from typing import ClassVar

from enough import K

from fspersistentdict.dircoll import DirectoryCollection
from fspersistentdict.keyedcachedcollection import KeyedCachedCollection


class KeyedDirectoryCollection(
    DirectoryCollection[K], KeyedCachedCollection[K]
):
    _ID_PATH: ClassVar[str] = '.count'

    @abstractmethod
    def _load_key(self, path: str) -> K:
        ...

    def _dir(self, key: K) -> str:
        return self._abs(str(hash(key)))

    def _find(self, key: K) -> str | None:
        dir_path = self._dir(key)
        if not os.path.exists(dir_path):
            return None
        for k, obj_path in self._sub_iter(dir_path):
            if k == key:
                return obj_path
            self._present_cache.add(k)
        return None

    def _id_path(self, dir_path: str) -> str:
        return os.path.join(dir_path, self._ID_PATH)

    def _inc_id(self, dir_path: str) -> str:
        with open(self._id_path(dir_path), 'r+') as f:
            current = int(f.read())
            f.seek(0)
            f.write(str(current + 1))
        return os.path.join(dir_path, str(current))

    def _init_dir(self, dir_path: str) -> None:
        os.mkdir(dir_path)
        with open(self._id_path(dir_path), 'w') as f:
            f.write('0')

    def _rm_if_empty(self, dir_path: str) -> None:
        if len(os.listdir(dir_path)) == 1:
            os.remove(self._id_path(dir_path))
            os.rmdir(dir_path)

    def _sub_iter(self, path: str) -> Iterator[tuple[K, str]]:
        for obj_path in self._obj_paths(path):
            yield self._load_key(obj_path), obj_path

    def _contains(self, key: K) -> bool:
        return bool(self._find(key))

    def _iter(self) -> Iterator[K]:
        for obj_path in self._obj_paths(self._path):
            yield from self._sub_iter(obj_path)

    def __init__(self, path: str, new: bool) -> None:
        DirectoryCollection.__init__(self, path, new)
        KeyedCachedCollection.__init__(self)

    def __contains__(self, key: K) -> bool:
        self._require_valid()
        return super().__contains__(key)

    def __iter__(self) -> Iterator[K]:
        self._require_valid()
        return super().__iter__()
