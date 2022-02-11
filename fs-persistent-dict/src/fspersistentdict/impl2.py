from __future__ import annotations

import base64
import os
import pickle
from abc import abstractmethod
from collections.abc import Collection, Iterable, Iterator, MutableMapping, MutableSequence, MutableSet
from io import BufferedIOBase, BytesIO
from typing import Callable, Final, Generic

import enough as br
from enough import Sentinel, K, T, V


_SENTINEL: Final[Sentinel] = Sentinel()


class DirectoryCollection(Collection[T], Generic[T]):
    # Mapping from mode names to factories for making a DirectoryCollection in that mode given its root path and
    # contents.
    _MODE_TO_FACTORY: Final[dict[str, Callable[[str], DirectoryCollection]]] = {}

    # Name of the path component for the file which specifies the type of collection a directory corresponds to.
    _MODE_COMP: Final[str] = '.mode'

    # What mode are we using?
    _mode: str

    # Path to the root of this persistent collection.
    _root: str | None

    @staticmethod
    def _encoded_file_name(key: T) -> str:
        return base64.encodebytes(pickle.dumps(key)).decode('ASCII').replace('/', '$')

    @staticmethod
    def _load_collection(path: str) -> Collection[T]:
        mode_file = os.path.join(path, DirectoryCollection._MODE_COMP)
        if not os.path.isfile(mode_file):
            raise FileNotFoundError('Mode file not found.')
        with open(mode_file) as f:
            mode_str = f.read()
        if (factory := DirectoryCollection._MODE_TO_FACTORY.get(mode_str)) is None:
            raise OSError(f'Mode file {mode_file} has unrecognized mode string {mode_str}.')
        return factory(path)

    @staticmethod
    def load(path: str) -> tuple[SimpleType, RealType]:
        bytes_io = BytesIO()
        bytes_io.write(base64.decodestring(path.replace('$', '/').encode('ASCII')))
        key = TypeEncoder.decode(bytes_io)
        if os.path.isfile(path):
            with open(path, 'rb') as f:
                # noinspection PyTypeChecker
                value = TypeEncoder.decode(f)
        elif os.path.isdir(path):
            value = DirectoryCollection._load_collection(path)
        else:
            raise FileNotFoundError(path)
        return key, value

    @staticmethod
    def load_root(path: str) -> Collection[T]:
        if not os.path.isdir(path):
            raise NotADirectoryError(path)
        return DirectoryCollection._load_collection(path)

    def _abs(self, path: str) -> str:
        return os.path.join(self._root, path)

    @abstractmethod
    def _decode(self, path: str) -> T:
        ...

    @abstractmethod
    def _encode(self, key: T) -> str:
        ...

    def _ls(self) -> list[str]:
        return os.listdir(self._root)

    @classmethod
    @abstractmethod
    def _mode(cls) -> str:
        ...

    @property
    def _mode_path(self) -> str:
        return os.path.join(self._root, self._MODE_COMP)

    def _path(self, key: SimpleType) -> str:
        return self._abs(self._encoded_file_name(key))

    def _rename(self, from_key: SimpleType, to_key: SimpleType) -> None:
        with self._lock:
            os.rename(self._path(from_key), self._path(to_key))

    def __init__(self, root: str) -> None:
        self._root = root
        if not os.path.isdir(root):
            try:
                os.mkdir(root)
            except FileNotFoundError:
                raise FileNotFoundError(f'Parent of root directory {root} does not exist.') from None
            with open(os.path.join(self._root, self._MODE_COMP), 'w') as f:
                f.write(self._mode())

    def __iter__(self) -> Iterator[T]:
        for path in self._ls():
            if path != self._MODE_COMP:
                yield self._decode(path)

    def __len__(self) -> int:
        return len(self._ls()) - 1


class DirectoryMap2(MutableMapping[K, V], DirectoryCollection[K]):
    @staticmethod
    def _decode_value(buffer: BufferedIOBase) -> V:
        # noinspection PyTypeChecker
        return pickle.load(buffer)

    @staticmethod
    def _encode_value(value: V, file: BufferedIOBase) -> None:
        # noinspection PyTypeChecker
        pickle.dump(value, file)

    def _decode(self, path: str) -> K:
        return pickle.loads(base64.decodebytes(bytes(path.replace('$', '/'), 'ASCII')))

    def _encode(self, key: K) -> str:
        return str(base64.encodebytes(pickle.dumps(key))).replace('/', '$')

    def __getitem__(self, key: K) -> V:
        with open(self._path(key), 'rb') as file:
            # noinspection PyTypeChecker
            return self._decode_value(file)

    def __setitem__(self, key: K, value: V) -> None:
        


class KeyedDirectoryCollection(DirectoryCollection[SimpleType]):
    # Buffer to use to decode objects from paths.
    _buffer: BytesIO

    def __init__(self, root: str, mode: str) -> None:
        super().__init__(root, mode)
        self._buffer = BytesIO()

    def _decode(self, path: str) -> SimpleType:
        with self._lock:
            self._buffer.write(path.encode('ASCII'))
            return TypeEncoder.decode(self._buffer)

    def __contains__(self, key: SimpleType) -> bool:
        with self._working():
            return os.path.exists(self._path(key))


class ValuedDirectoryCollection(DirectoryCollection[T], Generic[K, T]):
    @staticmethod
    def _get(path: str) -> RealType | Sentinel:
        try:
            return DirectoryCollection.load(path)[1]
        except FileNotFoundError:
            return _SENTINEL

    @staticmethod
    def _set(path: str, value: RealType) -> None:
        if isinstance(value, DirectoryCollection):
            value.copy(path)
        else:
            with open(path, 'wb') as f:
                # noinspection PyTypeChecker
                TypeEncoder.encode(value, f)

    def swap(self, key1: K, key2: K) -> None:
        path1, path2 = self._path(key1), self._path(key2)
        with self._working():
            br.fs.swap(path1, path2)


class DirectoryMap(
    MutableMapping[SimpleType, RealType], KeyedDirectoryCollection, ValuedDirectoryCollection[SimpleType, SimpleType]
):
    def __delitem__(self, key: SimpleType) -> None:
        path = self._path(key)
        with self._working():
            if not br.rm(path, recursive=True, force=True):
                raise KeyError(key)
            self._len -= 1

    def __getitem__(self, key: K) -> RealType:
        with self._working():
            if (item := self._get(self._path(key))) is _SENTINEL:
                raise KeyError(key)
            return item

    def __setitem__(self, key: K, value: RealType) -> None:
        path = self._abs(key)
        with self._working():
            if not br.rm(path, recursive=True, force=True):
                self._len += 1
            self._set(path, value)

    def move(self, src_key: SimpleType, dest_key: SimpleType, replace: bool = False) -> None:
        src_path = self._path(src_key)
        dest_path = self._path(dest_key)
        with self._working():
            if replace and br.rm(dest_path, recursive=True, force=True):
                self._len -= 1
            os.rename(src_path, dest_path)


class DirectorySeq(MutableSequence[RealType], ValuedDirectoryCollection[int | slice, RealType | Iterable[RealType]]):
    def _idxs(self, idx_or_slice: int | slice) -> range:
        try:
            return br.idx_range(idx_or_slice, len(self))
        except IndexError:
            raise IndexError(f'{type(self).__name__} object index out of range') from None
        except TypeError:
            raise TypeError(
                f'{type(self).__name__} indices must be integers or slices, not {type(idx_or_slice).__name__}'
            ) from None

    def _insert(self, idx: int, values: Iterable[RealType], length: int) -> None:
        for i in range(len(self) - 1, idx - 1, -1):
            self._rename(i, i + length)
        for i, obj in enumerate(values, idx):
            self._set(self._path(i), obj)

    def _decode(self, path: str) -> RealType:
        with self._lock:
            item = self._get(path)
            if item is _SENTINEL:
                raise FileNotFoundError(f'Could not find path element {path} while iterating over DirectorySeq.')
            return item

    def __delitem__(self, idx_or_slice: int | slice) -> None:
        with self._working():
            idxs = self._idxs(idx_or_slice)
            step = idxs.step
            if idxs:
                num_to_delete = len(idxs)
                if step < 0:
                    # Much less headache and room for error if we delete in a positively-oriented fashion.
                    idxs = reversed(idxs)
                for i, j in enumerate(idxs):
                    br.rm(self._path(j), recursive=True, force=True)
                    # In case step != 1, shift down elements from j + 1 to j + step (right-exclusive as usual) by the
                    # number of elements deleted so far, which is i + 1.
                    # On the other hand, if we are looking at the last element, do this from all elements from j + 1 to
                    # the end of this sequence.
                    end = len(self) if i == num_to_delete - 1 else j + step
                    for k in range(j + 1, end):
                        self._rename(k, k - i - 1)
                self._len -= num_to_delete

    def __getitem__(self, idx_or_slice: int | slice) -> RealType | list[RealType]:
        result = []
        with self._working():
            for i in self._idxs(idx_or_slice):
                path = self._path(i)
                item = self._get(path)
                if item is _SENTINEL:
                    # Should not happen, but if it does we want an exception to be raised.
                    raise FileNotFoundError(f'File {path} for index {i} no longer exists.')
                result.append(item)
        if isinstance(idx_or_slice, int):
            return result[0]
        return result

    def __iter__(self) -> Iterator[RealType]:
        buffer = BytesIO()
        with self._working():
            contents = os.listdir(self._root)
        for path in contents:
            if path != self._MODE_COMP:
                with open(path, 'rb') as f:
                    # noinspection PyTypeChecker
                    yield TypeEncoder.decode(f)
                buffer.write(path.encode('ASCII'))
                yield TypeEncoder.decode(buffer)

    def __setitem__(self, idx_or_slice: int | slice, value: RealType | Iterable[RealType]) -> None:
        with self._working():
            idxs = self._idxs(idx_or_slice)
            step = idxs.step
            if isinstance(idx_or_slice, int):
                value = [value]
            elif not isinstance(value, Iterable):
                raise TypeError('can only assign an iterable')
            if not isinstance(value, Collection):
                value = list(value)
            n = len(value)
            m = len(idxs)
            if step != 1 and n != m:
                raise ValueError(f'attempt to assign sequence of size {n} to extended slice of size {m}')
            value_iter = iter(value)
            for i, obj in zip(idxs, value_iter):
                self._set(self._path(i), obj)
            if n > m:
                self._insert(idxs.stop, value_iter, n - m)
                self._len += n - m
            elif n < m:
                del self[idxs[n]:idxs[n] + m - n]

    def insert(self, idx: int, value: RealType) -> None:
        if not isinstance(idx, int):
            raise TypeError(f"{type(idx).__name__} cannot be interpreted as an integer.")
        idx = self._idxs(idx)[0]
        self._insert(idx, [value], 1)
        self._len += 1


class DirectorySet(MutableSet[SimpleType], KeyedDirectoryCollection):
    def add(self, value: SimpleType) -> None:
        with self._working():
            path = self._path(value)
            if not os.path.exists(path):
                with open(path, 'wb'):
                    pass
                self._len += 1

    def discard(self, value: SimpleType) -> None:
        with self._working():
            if br.rm(self._path(value), recursive=True, force=True):
                self._len -= 1
