import os.path

from enough import K, V

from fspersistentdict.cachedmapping import CachedMapping
from fspersistentdict.dircoll import DirectoryCollection
from fspersistentdict.keyeddirectorycollection import KeyedDirectoryCollection


class DirectoryMap(KeyedDirectoryCollection[K], CachedMapping[K, V]):
    @staticmethod
    def _key_path(path: str) -> str:
        return os.path.join(path, 'k')

    @staticmethod
    def _value_path(path: str) -> str:
        return os.path.join(path, 'v')

    def _load_key(self, path: str) -> K:
        return self._load(self._key_path(path))

    @staticmethod
    def _load_value(path: str) -> V:
        return DirectoryCollection._load(DirectoryMap._value_path(path))

    @staticmethod
    def _save_entry(key: K, value: object, path: str) -> V:
        DirectoryCollection._save(key, DirectoryMap._key_path(path))
        return DirectoryCollection._save(value, DirectoryMap._value_path(path))

    def _del(self, key: K) -> None:
        path = self._find(key)
        if not path:
            raise KeyError(key)
        self._delete(path)
        self._rm_if_empty(os.path.dirname(path))

    def _get(self, key: K) -> V:
        path = self._find(key)
        if not path:
            raise KeyError(key)
        return self._load_value(path)

    def _set(self, key: K, value: object) -> tuple[V, bool]:
        path = self._find(key)
        if not path:
            dir_path = self._dir(key)
            if not os.path.exists(dir_path):
                self._init_dir(dir_path)
            path = self._inc_id(dir_path)
            return self._save_entry(key, value, path), True
        self._delete(self._value_path(path))
        return self._save_entry(key, value, path), False

    def __init__(self, path: str, new: bool) -> None:
        KeyedDirectoryCollection.__init__(self, path, new)
        CachedMapping.__init__(self)

    def __delitem__(self, key: K) -> None:
        self._require_valid()
        super().__delitem__(key)

    def __getitem__(self, key: K) -> V:
        self._require_valid()
        return super().__getitem__(key)

    def __setitem__(self, key: K, value: object) -> None:
        self._require_valid()
        super().__setitem__(key, value)
