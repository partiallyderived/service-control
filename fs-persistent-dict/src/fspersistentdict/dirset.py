import os
import os.path

from enough import K

from fspersistentdict.cachedset import CachedSet
from fspersistentdict.keyeddirectorycollection import KeyedDirectoryCollection


class DirectorySet(KeyedDirectoryCollection[K], CachedSet[K]):
    def _add(self, key: K) -> bool:
        if self._contains(key):
            return False
        dir_path = self._dir(key)
        if not os.path.exists(dir_path):
            self._init_dir(dir_path)
        path = self._inc_id(dir_path)
        self._save(key, path)
        return True

    def _discard(self, key: K) -> bool:
        obj_path = self._find(key)
        if not obj_path:
            return False
        os.remove(obj_path)
        dir_path = os.path.dirname(obj_path)
        self._rm_if_empty(dir_path)
        return True

    def _load_key(self, path: str) -> K:
        return self._load(path)

    def add(self, key: K) -> None:
        self._require_valid()
        super().add(key)

    def discard(self, key: K) -> None:
        self._require_valid()
        super().discard(key)

