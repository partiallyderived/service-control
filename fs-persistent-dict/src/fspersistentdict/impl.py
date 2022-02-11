from __future__ import annotations

import base64
import os
import shutil
import struct
from abc import ABC, abstractmethod
from collections.abc import ByteString, Collection, Iterable, Mapping, Set
from enum import Enum
from io import BufferedIOBase, BytesIO
from typing import Any, Final, Generic

from enough import T, T1, T2

_DICT_SENTINEL: Final[object] = object()


def purge_file(path: str) -> bool:
    if os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    else:
        return False
    return True


def purge_file_or_raise(path: str) -> None:
    if not purge_file(path):
        raise FileNotFoundError(path)


class MutateHookDict(dict[T1, T2], ABC, Generic[T1, T2]):
    @abstractmethod
    def _clear(self) -> None:
        ...

    def _del(self, key: T1) -> None:
        ...

    @abstractmethod
    def _set(self, key: T1, value: T2) -> None:
        ...

    def __delitem__(self, key: T1) -> None:
        super().__delitem__(key)
        self._del(key)

    def __ior__(self, other: Iterable[tuple[T1, T2]] | Mapping[T1, T2]) -> MutateHookDict[T1, T2]:
        super().__ior__(other)
        if isinstance(other, Mapping):
            other = other.items()
        for key, value in other:
            self[key] = value
        return self

    def __setitem__(self, key: T1, value: T2) -> None:
        super().__setitem__(key, value)
        self._set(key, value)

    def clear(self) -> None:
        super().clear()
        self._clear()

    def pop(self, key: T1, default: T2 = _DICT_SENTINEL) -> T2:
        if default is _DICT_SENTINEL or key in self:
            result = super().pop(key)
            self._del(result)
            return result
        return default

    def popitem(self) -> tuple[T1, T2]:
        key, value = super().popitem()
        self._del(key)
        return key, value

    def setdefault(self, key: T1, default: T2 | None = None) -> T2:
        if key in self:
            return self[key]
        self[key] = default
        return default

    def update(self, mapping: Iterable[tuple[T1, T2]] | Mapping[T1, T2] = _DICT_SENTINEL, **kwargs: Any) -> None:
        if mapping is not _DICT_SENTINEL:
            self.__ior__(mapping)
        for k, v in kwargs.items():
            self[k] = v


class MutateHookList(list[T], ABC, Generic[T]):
    @staticmethod
    def _range_index(idx: int, length: int) -> int:
        if idx < -length:
            return 0
        if idx < 0:
            return idx + length
        return idx

    @staticmethod
    def _slice_range(slc: slice, length: int) -> range:
        step = slc.step or 1
        pos_step = slc.step > 0
        if slc.start is None:
            start = 0 if pos_step else length - 1
        elif slc.start >= length:
            return range(0)
        else:
            start = MutateHookList._range_index(slc.start, length)
        if slc.stop is None:
            stop = length if pos_step else -1
        elif slc.stop >= length:
            stop = length
        else:
            stop = MutateHookList._range_index(slc.stop, length)
        return range(start, stop, step)

    @abstractmethod
    def _add(self, item: T) -> None:
        ...

    def _add_many(self, items: Iterable[T]) -> None:
        for item in items:
            self._add(item)

    @abstractmethod
    def _clear(self) -> None:
        ...

    def _del(self, idx: int) -> None:
        for i in range(idx, len(self)):
            self._move(i + 1, i)
        self._del_tail(1)

    @abstractmethod
    def _del_tail(self, n: int) -> None:
        ...

    def _del_range(self, idxs: range) -> None:
        old_len = len(self) + len(idxs)
        for i in idxs:
            if i != old_len - 1:
                self._move(i + 1, i)
        self._del_tail(old_len - len(self))

    def _insert(self, idx: int, item: T) -> None:
        self._insert_many(idx, [item])

    def _insert_many(self, idx: int, items: Collection[T]) -> None:
        n = len(items)
        old_len = len(self) - n
        self._make_space(n)
        for i in range(old_len - 1, idx - 1, -1):
            self._move(i, i + n)
        for i, item in enumerate(items, idx):
            self._set(i, item)
        for item in items:
            self._insert(idx, item)

    def _make_space(self, num: int) -> None:
        for _ in range(num):
            self._add(None)

    def _move(self, src_idx: int, dest_idx: int) -> None:
        self._set(dest_idx, self[src_idx])

    @abstractmethod
    def _set(self, idx: int, item: T) -> None:
        ...

    def _set_range(self, idxs: range, items: Collection[T]) -> None:
        for i, item in zip(idxs, items):
            self._set(i, item)

    def __delitem__(self, idx_or_slice: int | slice) -> None:
        old_len = len(self)
        super().__delitem__(idx_or_slice)
        if isinstance(idx_or_slice, slice):
            _range = self._slice_range(idx_or_slice, old_len)
            self._del_range(_range)
        else:
            self._del(idx_or_slice)

    def __iadd__(self, values: Iterable[T]) -> MutateHookList[T]:
        if not isinstance(values, Collection):
            values = list(values)
        super().__iadd__(values)
        self._add_many(values)
        return self

    def __imul__(self, by: int) -> MutateHookList[T]:
        super().__imul__(by)
        if by > 1:
            orig_len = len(self) // by
            self._add_many(self[i] for i in range(orig_len, len(self)))
        elif by < 1:
            self._clear()
        return self

    def __setitem__(self, idx_or_slice: int | slice, value: T | Iterable[T]) -> None:
        if isinstance(idx_or_slice, slice):
            if not isinstance(value, Collection):
                # Need copy of value since it is only an iterable, no guarantee we can iterate multiple times.
                value = list(value)
            old_len = len(self)
            super().__setitem__(idx_or_slice, value)
            _range = self._slice_range(idx_or_slice, old_len)
            len_diff = len(value) - len(_range)
            set_range = self._slice_range(idx_or_slice, len(self))
            self._set_range(set_range, value)
            if len_diff < 0:
                self._del_range(_range[len_diff:])
            elif len_diff > 0:
                # Can assume step == 1.
                self._insert_many(_range.stop - len_diff, value[-len_diff:])
        else:
            super().__setitem__(idx_or_slice, value)
            if idx_or_slice < 0:
                idx_or_slice += len(self)
            self._set(idx_or_slice, value)

    def append(self, obj: T) -> None:
        super().append(obj)
        self._add([obj])

    def clear(self) -> None:
        super().clear()
        self._clear()

    def extend(self, values: Iterable[T]) -> None:
        if not isinstance(values, Collection):
            values = list(values)
        super().extend(values)
        self._add_many(values)

    def insert(self, idx: int, item: T) -> None:
        super().insert(idx, item)
        if idx < 0:
            idx += len(self)
        self._insert(idx, item)

    def pop(self, idx: int = -1) -> T:
        popped = super().pop(idx)
        if idx < 0:
            idx += len(self) + 1
        self._del(idx)
        return popped

    def remove(self, value: T) -> None:
        idx = self.index(value)
        del self[idx]

    def reverse(self) -> None:
        if not len(self):
            return
        super().reverse()
        first = self[-1]
        for i in range(1, len(self) // 2):
            self._move(i, 0)
            self._move(len(self) - i - 1, i)
            self._move(0, len(self) - i - 1)
        self._move(len(self) - 1, 0)
        self._set(len(self) - 1, first)


class MutateSetHook(set[T], ABC, Generic[T]):
    @abstractmethod
    def _add(self, item: T) -> None:
        ...

    @abstractmethod
    def _clear(self) -> None:
        ...

    @abstractmethod
    def _del(self, item: T) -> None:
        ...

    def __iand__(self, other: Iterable[T]) -> MutateSetHook[T]:
        if not isinstance(other, Set):
            other = set(other)
        for obj in self:
            if obj not in other:
                self.remove(obj)
        return self

    def __isub__(self, other: Iterable[T]) -> MutateSetHook:
        if not isinstance(other, Collection):
            other = set(other)
        for obj in other:
            self.discard(obj)
        return self

    def __ior__(self, other: Iterable[T]) -> MutateSetHook[T]:
        for obj in other:
            if obj not in self:
                self.add(obj)
        return self

    def __ixor__(self, other: Iterable[T]) -> MutateSetHook[T]:
        for obj in other:
            if obj in self:
                self.remove(obj)
            else:
                self.add(obj)
        return self

    def add(self, obj: T) -> None:
        if obj not in self:
            super().add(obj)
            self._add(obj)

    def clear(self) -> None:
        super().clear()
        self._clear()

    def discard(self, obj: T) -> None:
        if obj in self:
            super().discard(obj)
            self._del(obj)

    def pop(self) -> T:
        result = super().pop()
        self._del(result)
        return result

    def remove(self, obj: T) -> None:
        super().remove(obj)
        self._del(obj)


class TypeCode(Enum):
    _ignore_ = '_INT_TO_CODE'

    NONE = 0, '', None
    FALSE = 1, '', False
    TRUE = 2, '', True
    INT = 3, 'i'
    LONG = 4, 'q'
    FLOAT = 5, 'd'
    STR = 6, 's'
    BYTES = 7, 'p'

    def __new__(cls, code: int, fmt: str, constant: bool | None = None) -> TypeCode:
        obj = object.__new__(cls)
        obj._value_ = code
        obj.code = code
        obj.constant = constant
        obj.fmt = fmt
        return obj

    @staticmethod
    def decode(inp: BufferedIOBase) -> SimpleType:
        raw_code = inp.read(1)
        if not raw_code:
            # EOF, relevant for sets.
            return None
        code = TypeCode(raw_code[0])
        if code.fmt:
            # noinspection PyTypeChecker
            return struct.unpack_from(code.fmt, inp)
        return code.constant

    @staticmethod
    def encode(obj: SimpleType, out: BufferedIOBase) -> None:
        code = TypeCode.from_obj(obj)
        out.write(bytes([code.code]))
        if code.fmt:
            struct.pack_into(code.fmt, out, obj)

    @staticmethod
    def from_obj(obj: SimpleType) -> TypeCode:
        match obj:
            case None:
                return TypeCode.NONE
            case False:
                return TypeCode.FALSE
            case True:
                return TypeCode.TRUE
            case int():
                if -(1 << 32) <= obj < (1 << 32):
                    return TypeCode.INT
                elif -(1 << 64) <= obj < (1 << 64):
                    return TypeCode.LONG
                else:
                    raise ValueError(f'ints which take more than 8 bytes to represent are not supported: {obj}')
            case float():
                return TypeCode.FLOAT
            case str():
                return TypeCode.STR
            case bytes():
                return TypeCode.BYTES
            case _:
                raise TypeError(f'objects of type {type(obj)} are not supported.')


SimpleType = int | float | bool | str | bytes | None
UserType = SimpleType | Iterable
RealType = 'SimpleType | FSPersistentCollection'


class FSPersistentCollection:
    _MODE_FILE = '.mode'

    # Path to the root of this persistent collection.
    _root: str

    @staticmethod
    def _encoded_file_name(key: SimpleType) -> str:
        out = BytesIO()
        TypeCode.encode(key, out)
        # Need to replace / with $ to have a proper file name.
        return base64.encodebytes(out.getvalue()).decode('ASCII').replace('/', '$')

    @staticmethod
    def _load_collection(path: str) -> FSPersistentCollection:
        mode_file = os.path.join(path, FSPersistentCollection._MODE_FILE)
        if not os.path.isfile(mode_file):
            raise FileNotFoundError('Mode file not found.')
        with open(mode_file) as f:
            mode_str = f.read()
        contents = {}
        for pth in os.listdir(path):
            if pth != FSPersistentCollection._MODE_FILE:
                full_path = os.path.join(path, pth)
                key, value = FSPersistentCollection.load(full_path)
                contents[key] = value
        match mode_str:
            case 'map':
                return FSPersistentDict(path, contents)
            case 'seq':
                return FSPersistentList(path, (contents[i] for i in range(len(contents))))
            case 'set':
                return FSPersistentSet(path, contents.keys())
            case _:
                raise EnvironmentError(f'Unrecognized mode string: {mode_str}')

    @staticmethod
    def load(path: str) -> tuple[SimpleType, RealType]:
        bytes_io = BytesIO()
        bytes_io.write(base64.decodestring(path.replace('$', '/').encode('ASCII')))
        key = TypeCode.decode(bytes_io)
        if os.path.isfile(path):
            with open(path, 'rb') as f:
                # noinspection PyTypeChecker
                value = TypeCode.decode(f)
        elif os.path.isdir(path):
            value = FSPersistentCollection._load_collection(path)
        else:
            raise FileNotFoundError(path)
        return key, value

    @staticmethod
    def load_root(path: str) -> FSPersistentCollection:
        if not os.path.isdir(path):
            raise NotADirectoryError(path)
        return FSPersistentCollection._load_collection(path)

    def _clear(self) -> None:
        for path in os.listdir(self._root):
            if path != self._MODE_FILE:
                full_path = os.path.join(self._root, path)
                purge_file_or_raise(full_path)

    def _del(self, key: SimpleType) -> None:
        purge_file_or_raise(self._file_name(key))

    def _file_name(self, key: SimpleType) -> str:
        return os.path.join(self._root, self._encoded_file_name(key))

    def _move(self, from_key: SimpleType, to_key: SimpleType) -> None:
        src = self._file_name(from_key)
        dest = self._file_name(to_key)
        os.rename(src, dest)

    def _set_item(self, key: SimpleType, value: UserType) -> RealType:
        file_name = self._file_name(key)
        if os.path.isdir(file_name):
            shutil.rmtree(file_name)
        if isinstance(value, Iterable) and not isinstance(value, (str, ByteString)):
            os.mkdir(file_name)
            if isinstance(value, Mapping):
                return FSPersistentDict(file_name, value)
            elif isinstance(value, Set):
                return FSPersistentSet(file_name, value)
            else:
                # Default to list.
                return FSPersistentList(file_name, value)
        with open(file_name, 'wb') as f:
            # noinspection PyTypeChecker
            TypeCode.encode(value, f)
        return value


class FSPersistentDict(FSPersistentCollection, MutateHookDict[SimpleType, UserType]):
    def __init__(
        self, root: str, contents: Iterable[tuple[SimpleType, UserType]] | Mapping[SimpleType, UserType] = ()
    ) -> None:
        super().__init__(contents)
        self._root = root

    def _set(self, key: SimpleType, value: UserType) -> None:
        dict.__setitem__(self, key, self._set_item(key, value))


class FSPersistentList(FSPersistentCollection, MutateHookList[RealType]):
    def __init__(self, root: str, contents: Iterable[RealType] = ()) -> None:
        self._root = root
        super().__init__(contents)

    def _add(self, item: UserType) -> None:
        self._set(len(self) - 1, item)

    def _add_many(self, items: Iterable[T]) -> None:
        if not isinstance(items, Collection):
            items = list(items)
        for i, item in enumerate(items, len(self) - len(items)):
            self._set(i, item)

    def _del(self, idx: int) -> None:
        MutateHookList._del(self, idx)

    def _del_tail(self, n: int) -> None:
        pass

    def _make_space(self, num: int) -> None:
        pass

    def _set(self, idx: int, item: UserType) -> None:
        list.__setitem__(self, idx, self._set_item(idx, item))


class FSPersistentSet(FSPersistentCollection, MutateSetHook[SimpleType]):
    def __init__(self, root: str, contents: Iterable[SimpleType]) -> None:
        self._root = root
        super().__init__(contents)

    def _add(self, item: SimpleType) -> None:
        file_name = self._file_name(item)
        with open(file_name, 'wb'):
            pass
