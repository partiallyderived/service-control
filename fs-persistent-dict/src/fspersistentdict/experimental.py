from abc import abstractmethod
from collections.abc import Callable, Collection, Iterable, MutableSequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from enough.types import T

CollType = TypeVar('CollType')
GetType = TypeVar('GetType')
IndexKey = TypeVar('IndexKey')
IndexValue = TypeVar('IndexValue')
KeyType = TypeVar('KeyType')
SetType = TypeVar('SetType')
SliceKey = TypeVar('SliceKey')
SliceValue = TypeVar('SliceValue')
CollType1 = TypeVar('CollType1')
GetType1 = TypeVar('GetType1')
KeyType1 = TypeVar('KeyType1')
SetType1 = TypeVar('SetType1')
CollType2 = TypeVar('CollType2')
GetType2 = TypeVar('GetType2')
KeyType2 = TypeVar('KeyType2')
SetType2 = TypeVar('SetType2')


class ItemCollection(Collection[CollType], Generic[CollType, GetType, KeyType, SetType]):
    def __delitem__(self, key: KeyType) -> None:
        ...

    def __getitem__(self, key: KeyType) -> GetType:
        ...

    def __setitem__(self, key: KeyType, value: SetType) -> None:
        ...


class MutableSeq(MutableSequence[T], ItemCollection[T, T | Iterable[T], int | slice, T | Iterable[T]]):
    pass


class ItemCollectionInterface(
    ItemCollection[CollType1, GetType1, KeyType1, SetType1],
    Generic[CollType1, GetType1, KeyType1, SetType1, CollType2, GetType2, KeyType2, SetType2]
):
    #: Underlying data.
    data: ItemCollection[CollType2, GetType2, KeyType2, SetType2]

    @abstractmethod
    def del_key(self, key: KeyType1) -> KeyType2:
        ...

    @abstractmethod
    def get_key(self, key: KeyType1) -> KeyType2:
        ...

    @abstractmethod
    def get_value(self, key: GetType2) -> GetType1:
        ...

    @abstractmethod
    def set_item(self, key: KeyType1, value: SetType1) -> tuple[KeyType2, SetType2]:
        ...

    def __delitem__(self, key: KeyType1) -> None:
        del self.data[self.del_key(key)]

    def __getitem__(self, key: KeyType1) -> GetType1:
        return self.get_value(self.data[self.get_key(key)])

    def __setitem__(self, key: KeyType1, value: SetType1) -> None:
        key, value = self.set_item(key, value)
        self.data[key] = value

    def __init__(self, data: ItemCollection[CollType2, GetType2, KeyType2, SetType2]) -> None:
        self.data = data


@dataclass
class FunctionalItemCollectionInterface(
    ItemCollectionInterface[CollType1, GetType1, KeyType1, SetType1, CollType2, GetType2, KeyType2, SetType2]
):
    #: Underlying data.
    data: ItemCollection[CollType2, GetType2, KeyType2, SetType2]

    #: Function to use to translate keys in a deletion context.
    del_key_fn: Callable[[KeyType1], KeyType2]

    #: Function to use to translate keys in a get context.
    get_key_fn: Callable[[KeyType1], KeyType2]

    #: Function to use to translate values in a get context.
    get_val_fn: Callable[[GetType2], GetType1]

    # Function to use to translate a key value pair in the context of setting an item.
    set_item_fn: Callable[[KeyType1, SetType1], tuple[KeyType2, SetType2]]

    def del_key(self, key: KeyType1) -> KeyType2:
        return self.del_key_fn(key)

    def get_key(self, key: KeyType1) -> KeyType2:
        return self.get_key_fn(key)

    def get_value(self, key: GetType2) -> GetType1:
        return self.get_val_fn(key)

    def set_item(self, key: KeyType1, value: SetType1) -> tuple[KeyType2, SetType2]:
        return self.set_item_fn(key, value)


class SeqKeyTranslator(Generic[IndexKey, SliceKey]):
    def index_key(self, idx: int) -> IndexKey:
        return idx

    def slice_key(self, slc: slice) -> SliceKey:
        return slc

    def __call__(self, idx_or_slc: int | slice) -> IndexKey | SliceKey:
        match idx_or_slc:
            case int():
                return self.index_key(idx_or_slc)
            case slice():
                return self.slice_key(idx_or_slc)
            case _:
                raise TypeError()


class SeqItemTranslator(Generic[T, IndexKey, IndexValue, SliceKey, SliceValue]):
    def index_item(self, idx: int, value: T) -> tuple[IndexKey, IndexValue]:
        return idx, value

    def slice_item(self, slc: slice, values: Iterable[T]) -> tuple[SliceKey, SliceValue]:
        return slc, values

    def __call__(
        self, idx_or_slc: int | slice, value: T | Iterable[T]
    ) -> tuple[IndexKey | SliceKey, IndexValue | SliceValue]:
        match idx_or_slc:
            case int():
                return self.index_item(idx_or_slc, value)
            case slice():
                return self.slice_item(idx_or_slc, value)
            case _:
                raise TypeError()


class MutableSeqInterface(
    MutableSeq[T],
    ItemCollectionInterface[
        T,
        T | Iterable[T],
        int | slice,
        T | Iterable[T],
        CollType2,
        GetType2,
        IndexKey | SliceKey,
        IndexValue | SliceValue
    ],
):
    @property
    @abstractmethod
    def del_translator(self) -> SeqKeyTranslator[IndexKey, SliceKey]:
        ...

    @property
    @abstractmethod
    def get_translator(self) -> SeqKeyTranslator[IndexKey, SliceKey]:
        ...

    @property
    @abstractmethod
    def set_translator(self) -> SeqItemTranslator[T, IndexKey, IndexValue, SliceKey, SliceValue]:
        ...

    def del_key(self, idx_or_slc: int | slice) -> IndexKey | SliceKey:
        return self.del_translator(idx_or_slc)

    def get_key(self, idx_or_slc: int | slice) -> IndexKey | SliceKey:
        return self.get_translator(idx_or_slc)

    def set_item(
        self, idx_or_slc: int | slice, value: T | Iterable[T]
    ) -> tuple[IndexKey | SliceKey, IndexValue | SliceValue]:
        return self.set_translator(idx_or_slc)
