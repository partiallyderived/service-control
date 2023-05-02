import random
import typing
from collections import *
from collections.abc import *
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from dataclasses import dataclass
from types import NoneType
from typing import Any, Concatenate, Generic, ParamSpec

import enough
from enough.exceptions import EnoughTypingErrors
from enough.typing import GenericType, T1, T2, TypeArg

# Define some additional ParamSpecs for testing.
P1 = ParamSpec('P1')
P2 = ParamSpec('P2')
P3 = ParamSpec('P3')

# These groups define a tuple wherein the first element is a tuple of
# subclasses, the second element is a tuple of classes where are all
# superclasses of the subclasses in the first element, and the third class is
# the number of type parameters each class takes. These groups are used to run
# tests for various standard generic types which share the same type parameters.
ITERABLE_GROUP = (Iterable, Iterator, Reversible, Collection), (Iterable,), 1
CONTAINER_GROUP = (Container,), (Container,), 1
COLLECTION_GROUP = (
    (Collection, Sequence, Set, ValuesView),
    (Collection,) + ITERABLE_GROUP[1] + CONTAINER_GROUP[1],
    1
)
SEQUENCE_GROUP = (Sequence,), (Sequence,) + COLLECTION_GROUP[1], 1
MUTABLE_SEQUENCE_GROUP = (
    (MutableSequence, UserList, list, deque),
    (MutableSequence,) + SEQUENCE_GROUP[1],
    1
)
SET_GROUP = (Set, KeysView, frozenset), (Set,) + COLLECTION_GROUP[1], 1
MUTABLE_SET_GROUP = (MutableSet, set), (MutableSet,) + SET_GROUP[1], 1
MAPPING_GROUP = (Mapping,), (Mapping,), 2
MUTABLE_MAPPING_GROUP = (
    (MutableMapping, ChainMap, OrderedDict, UserDict, defaultdict, dict),
    (MutableMapping,) + MAPPING_GROUP[1],
    2
)
ASYNC_ITERABLE_GROUP = (AsyncIterable, AsyncIterator), (AsyncIterable,), 1
ONE_OFFS = (
    (AbstractAsyncContextManager, 1),
    (AbstractContextManager, 1),
    (Awaitable, 1),
    (AsyncGenerator, 2),
    (Coroutine, 3),
    (Generator, 3)
)

ALL_GROUPS = (
    ITERABLE_GROUP,
    CONTAINER_GROUP,
    COLLECTION_GROUP,
    SEQUENCE_GROUP,
    MUTABLE_SEQUENCE_GROUP,
    SET_GROUP,
    MUTABLE_SET_GROUP,
    MAPPING_GROUP,
    MUTABLE_MAPPING_GROUP,
    ASYNC_ITERABLE_GROUP
) + tuple(((t,), (t,), args) for t, args in ONE_OFFS)

random.seed(1234)

# Choices to use to generate a random type.
TYPE_CHOICES: tuple[type[object], ...] = (
    NoneType, bool, int, float, str, tuple, list, set, frozenset, dict
)


def gen_type() -> TypeArg:
    nxt = random.choice(TYPE_CHOICES)
    if nxt in {list, set, frozenset}:
        if random.choice([False, True]):
            # Give a parameter.
            # noinspection PyUnresolvedReferences
            return nxt[gen_type()]
        # Omit a parameter.
        return nxt
    if nxt is dict:
        if random.choice([False, True]):
            # noinspection PyUnresolvedReferences
            return nxt[gen_type(), gen_type()]
    if nxt is tuple:
        if random.choice([False, True]):
            args = []
            while random.choice([False, True]):
                args.append(gen_type())
            return tuple[tuple(args)]
    return nxt


def test_infer_type_args() -> None:
    # These tests use some randomness in order to test a variety of types. Set a
    # seed for consistent results.

    # Trivial test for built-in types first.
    assert enough.infer_type_args(list, list) == list[Any]
    assert enough.infer_type_args(list[int], list) == list[int]
    assert enough.infer_type_args(dict, dict) == dict[Any, Any]
    assert enough.infer_type_args(dict[int, str], dict) == dict[int, str]
    assert enough.infer_type_args(
        dict[tuple[str, bool, float], dict[str, int]], dict
    ) == dict[tuple[str, bool, float], dict[str, int]]

    # Thanks to get_origin, should also work with aliases defined in typing.
    assert enough.infer_type_args(typing.List, list) == list[Any]
    assert enough.infer_type_args(typing.List[str], list) == list[str]
    assert enough.infer_type_args(typing.Dict, dict) == dict[Any, Any]
    assert enough.infer_type_args(typing.Dict[int, str], dict) == dict[int, str]

    # Because issubclass(list, Iterable) is True due to subclass hooks, this
    # works even though Iterable is not in list.mro(). This is possible because
    # enough.infer_type_args recognizes that their type variables correspond to
    # each other.
    assert enough.infer_type_args(list, Iterable) == Iterable[Any]
    assert enough.infer_type_args(list[float], Iterable) == Iterable[float]
    assert enough.infer_type_args(list[int], Sequence) == Sequence[int]
    assert enough.infer_type_args(dict, Mapping) == Mapping[Any, Any]
    assert enough.infer_type_args(
        dict[int, float], Mapping
    ) == Mapping[int, float]
    assert enough.infer_type_args(
        dict[str, bool], MutableMapping
    ) == MutableMapping[str, bool]

    # Of course, collections defined in the standard modules collections and
    # collections.abc do explicitly subclass each
    # other, so type parameters may be inferred for them too.
    assert enough.infer_type_args(Iterable, Iterable) == Iterable[Any]
    assert enough.infer_type_args(Iterable[int], Iterable) == Iterable[int]
    assert enough.infer_type_args(Sequence[float], Iterable) == Iterable[float]
    assert enough.infer_type_args(
        MutableMapping[str, Any], Mapping
    ) == Mapping[str, Any]
    assert (
        enough.infer_type_args(OrderedDict[int, str], MutableMapping)
        == MutableMapping[int, str]
    )

    # Before moving on to more complicated cases, perform trivial tests for many
    # standard types.
    @dataclass
    class TrivialInferenceTester:
        # The number of parameters each of these types uses.
        subclasses: tuple[GenericType, ...]
        superclasses: tuple[GenericType, ...]
        num_vars: int

        def run(self, num_trials: int) -> None:
            # For each subclass and superclass pair, do num_trials trials
            # wherein the child class's type arguments are tested to see if they
            # match up with the parent class's type arguments.
            for subclass in self.subclasses:
                for superclass in self.superclasses:
                    assert issubclass(
                        typing.get_origin(subclass) or subclass, superclass
                    )
                    assert (
                        enough.infer_type_args(subclass, superclass)
                        == superclass[(Any,) * self.num_vars]
                    )
                    for i in range(num_trials):
                        args = tuple(gen_type() for _ in range(self.num_vars))
                        assert (
                            enough.infer_type_args(subclass[args], superclass)
                            == superclass[args]
                        )

    for subclasses, superclasses, num_vars in ALL_GROUPS:
        TrivialInferenceTester(subclasses, superclasses, num_vars).run(5)

    # Try to infer tuple args, which are handled specially.
    # (Any, ...) are the default type arguments for tuple.
    assert enough.infer_type_args(tuple, tuple) == tuple[Any, ...]
    assert enough.infer_type_args(
        tuple[int, str, float], tuple
    ) == tuple[int, str, float]
    assert enough.infer_type_args(tuple, Iterable) == Iterable[Any]
    assert enough.infer_type_args(tuple[int, str], Iterable) == Iterable[Any]
    # Tuples of uniform type correctly infer the element type argument for
    # iterables.
    assert enough.infer_type_args(tuple[int, ...], Iterable) == Iterable[int]
    assert enough.infer_type_args(tuple[int], Iterable) == Iterable[int]

    # A few examples with subclasses of tuple.
    class TupleChildNoArgs(tuple): pass
    class TupleChildArgs(tuple[int, str, float]): pass
    class TupleChildArgsChild(TupleChildArgs): pass

    assert enough.infer_type_args(TupleChildNoArgs, tuple) == tuple[Any, ...]
    assert enough.infer_type_args(
        TupleChildArgs, tuple
    ) == tuple[int, str, float]
    assert enough.infer_type_args(
        TupleChildArgsChild, tuple
    ) == tuple[int, str, float]

    # Do a few simple tests with Callable. More complicated tests are done
    # below.
    assert enough.infer_type_args(Callable, Callable) == Callable[..., Any]
    assert enough.infer_type_args(
        Callable[[int, str], float], Callable
    ) == Callable[[int, str], float]

    # Subclasses of Iterable or Iterator with additional type arguments.
    assert enough.infer_type_args(Mapping, Iterable) == Iterable[Any]
    # First type argument of Mappings corresponds to Iterable, Collection, etc.
    assert enough.infer_type_args(
        MutableMapping[int, float], Iterable
    ) == Iterable[int]
    assert enough.infer_type_args(Generator, Iterable) == Iterable[Any]
    # First type argument of Generator also corresponds to Iterable.
    assert enough.infer_type_args(
        Generator[tuple[int, float], bool, NoneType], Iterable
    ) == Iterable[tuple[int, float]]

    # Do the same with AsyncIterator.
    assert enough.infer_type_args(
        AsyncGenerator, AsyncIterator
    ) == AsyncIterator[Any]
    assert enough.infer_type_args(
        AsyncGenerator[int, str], AsyncIterable
    ) == AsyncIterable[int]

    # Coroutine is a subclass of Awaitable. The third type argument of Coroutine
    # should be the same as the type argument for Awaitable.
    assert enough.infer_type_args(Coroutine, Awaitable) == Awaitable[Any]
    assert enough.infer_type_args(
        Coroutine[int, str, float], Awaitable
    ) == Awaitable[float]

    # Types.
    assert enough.infer_type_args(int, type) == type[int]
    assert enough.infer_type_args(str, type) == type[str]
    assert enough.infer_type_args(
        AsyncGenerator[int, str], type
    ) == type[AsyncGenerator[int, str]]

    # Test some special cases.
    assert enough.infer_type_args(ByteString, Sequence) == Sequence[int]
    assert enough.infer_type_args(Counter, Mapping) == Mapping[Any, int]
    assert enough.infer_type_args(
        Counter[str], MutableMapping
    ) == MutableMapping[str, int]
    assert enough.infer_type_args(
        ItemsView, Iterable
    ) == Iterable[tuple[Any, Any]]
    assert enough.infer_type_args(
        ItemsView[int, str], Collection
    ) == Collection[tuple[int, str]]
    assert enough.infer_type_args(
        bytearray, MutableSequence
    ) == MutableSequence[int]
    assert enough.infer_type_args(bytes, Sequence) == Sequence[int]
    assert enough.infer_type_args(
        enumerate, Iterator
    ) == Iterator[tuple[int, Any]]
    assert enough.infer_type_args(memoryview, Sequence) == Sequence[int]
    assert enough.infer_type_args(range, Sequence) == Sequence[int]

    # Thanks to subclass hooks, we can get desirable behavior by default even
    # from non-generic subclasses. Though, since they aren't actually generic,
    # we can't actually check the results of parameterizations of them.
    assert enough.infer_type_args(type(iter(())), Iterator) == Iterator[Any]
    assert enough.infer_type_args(type(iter([])), Iterator) == Iterator[Any]
    assert enough.infer_type_args(type(iter({})), Iterator) == Iterator[Any]
    assert enough.infer_type_args(type(iter(set())), Iterator) == Iterator[Any]
    assert enough.infer_type_args(type({}.keys()), KeysView) == KeysView[Any]
    assert enough.infer_type_args(
        type({}.values()), ValuesView
    ) == ValuesView[Any]
    assert enough.infer_type_args(
        type({}.items()), ItemsView
    ) == ItemsView[Any, Any]
    assert enough.infer_type_args(
        type({}.items()), Iterable
    ) == Iterable[tuple[Any, Any]]

    # No standard abstract base class specification is complete without this
    # class.
    class VeryAbstractClass(
        AbstractAsyncContextManager,
        AbstractContextManager,
        AsyncGenerator,
        Coroutine,
        Generator,
        Mapping
    ): pass

    # Check that all relevant type parameters defaulted to Any.
    assert enough.infer_type_args(
        VeryAbstractClass, AbstractAsyncContextManager
    ) == AbstractAsyncContextManager[Any]
    assert enough.infer_type_args(
        VeryAbstractClass, AbstractContextManager
    ) == AbstractContextManager[Any]
    assert enough.infer_type_args(
        VeryAbstractClass, AsyncGenerator
    ) == AsyncGenerator[Any, Any]
    assert enough.infer_type_args(
        VeryAbstractClass, Coroutine
    ) == Coroutine[Any, Any, Any]
    assert enough.infer_type_args(
        VeryAbstractClass, Generator
    ) == Generator[Any, Any, Any]
    assert enough.infer_type_args(
        VeryAbstractClass, Mapping
    ) == Mapping[Any, Any]

    # Now with some type arguments specified.
    class LessAbstractClass(
        AbstractAsyncContextManager[NoneType],
        AbstractContextManager[bool],
        AsyncGenerator,
        Coroutine,
        Generator[tuple[bool, int], float, str],
        Mapping[tuple[bool, int], list[float]]
    ): pass

    # Check that type parameters with types omitted defaulted to Any, while
    # explicitly specified ones were set correctly.
    assert enough.infer_type_args(
        LessAbstractClass, AbstractAsyncContextManager
    ) == AbstractAsyncContextManager[NoneType]
    assert enough.infer_type_args(
        LessAbstractClass, AbstractContextManager
    ) == AbstractContextManager[bool]
    assert enough.infer_type_args(
        LessAbstractClass, AsyncGenerator
    ) == AsyncGenerator[Any, Any]
    assert enough.infer_type_args(
        LessAbstractClass, Coroutine
    ) == Coroutine[Any, Any, Any]
    assert enough.infer_type_args(
        LessAbstractClass, Generator
    ) == Generator[tuple[bool, int], float, str]
    assert enough.infer_type_args(
        LessAbstractClass, Mapping
    ) == Mapping[tuple[bool, int], list[float]]
    assert enough.infer_type_args(
        LessAbstractClass, Iterable
    ) == Iterable[tuple[bool, int]]

    # Now to actually try some examples with Generic.
    class Gen1(Generic[T1]): pass
    class Gen2(Gen1): pass
    class Gen3(Gen1[int]): pass
    class Gen4(Gen1[tuple[T1, T2]]): pass
    class Gen5(Gen4): pass
    class Gen6(Gen4[int, str]): pass
    class Gen7(Generic[T2]): pass
    class Gen8(Gen1, Gen7): pass
    class Gen9(Gen1[int], Gen7): pass
    class Gen10(Gen1, Gen7[int]): pass
    class Gen11(Gen1[int], Gen7[str]): pass

    assert enough.infer_type_args(Gen1, Gen1) == Gen1[Any]
    assert enough.infer_type_args(Gen1[int], Gen1) == Gen1[int]
    assert enough.infer_type_args(Gen2, Gen1) == Gen1[Any]
    assert enough.infer_type_args(Gen3, Gen1) == Gen1[int]
    assert enough.infer_type_args(Gen4, Gen1) == Gen1[tuple[Any, Any]]
    assert enough.infer_type_args(Gen4[int, str], Gen1) == Gen1[tuple[int, str]]
    assert enough.infer_type_args(Gen5, Gen1) == Gen1[tuple[Any, Any]]
    assert enough.infer_type_args(Gen5, Gen4) == Gen4[Any, Any]
    assert enough.infer_type_args(Gen6, Gen1) == Gen1[tuple[int, str]]
    assert enough.infer_type_args(Gen6, Gen4) == Gen4[int, str]
    assert enough.infer_type_args(Gen8, Gen1) == Gen1[Any]
    assert enough.infer_type_args(Gen8, Gen7) == Gen7[Any]
    assert enough.infer_type_args(Gen9, Gen1) == Gen1[int]
    assert enough.infer_type_args(Gen9, Gen7) == Gen7[Any]
    assert enough.infer_type_args(Gen10, Gen1) == Gen1[Any]
    assert enough.infer_type_args(Gen10, Gen7) == Gen7[int]
    assert enough.infer_type_args(Gen11, Gen1) == Gen1[int]
    assert enough.infer_type_args(Gen11, Gen7) == Gen7[str]

    # Test mixing of Generic subclasses and standard generic types.
    class Mixed1(Mapping, Generic[T1, T2]): pass
    class Mixed2(Mapping[T1, T2], Generic[T1, T2]): pass
    class Mixed3(Mapping[int, bool], Generic[T1, T2]): pass

    assert enough.infer_type_args(Mixed1, Mapping) == Mapping[Any, Any]
    assert enough.infer_type_args(Mixed1, Iterable) == Iterable[Any]
    assert enough.infer_type_args(Mixed2, Mapping) == Mapping[Any, Any]
    assert enough.infer_type_args(Mixed2, Iterable) == Iterable[Any]
    assert enough.infer_type_args(Mixed3, Mapping) == Mapping[int, bool]
    assert enough.infer_type_args(Mixed3, Iterable) == Iterable[int]

    # Try some more complicated examples with ParamSpec and Concatenate.
    # This does not work as expected if Generic appears before Callable as then
    # this class inherits Callables behavior when arguments are passed to it.
    # Note that inferred type param arguments will always be flattened and
    # consequence occurrences of ... will collapse into a single occurrence.
    # noinspection PyTypeHints
    class Complicated(
        Generic[P1, T1, T2, P2, P3],
        Callable[Concatenate[P1, T2, P2, P3], tuple[T1, T2]]
    ): pass
    assert enough.infer_type_args(
        Complicated, Complicated
    ) == Complicated[..., Any, Any, ..., ...]
    assert enough.infer_type_args(
        Complicated, Callable
    ) == Callable[[..., Any, ...], tuple[Any, Any]]
    assert enough.infer_type_args(
        Complicated[[int, str], bool, float, [NoneType, list[int]], [str, int]],
        Complicated
    ) == Complicated[[int, str], bool, float, [NoneType, list[int]], [str, int]]
    assert enough.infer_type_args(
        Complicated[[int, str], bool, float, [NoneType, list[int]], [str, int]],
        Callable
    ) == Callable[
        [int, str, float, NoneType, list[int], str, int], tuple[bool, float]
    ]
    assert enough.infer_type_args(
        Complicated[[int, str], bool, float, ..., ...], Callable
    ) == Callable[[int, str, float, ...], tuple[bool, float]]

    # Child is not a type.
    with enough.raises(EnoughTypingErrors.ChildNotType(3)):
        enough.infer_type_args(3, list)

    # Parent is not a type.
    with enough.raises(EnoughTypingErrors.ParentNotType('parent')):
        enough.infer_type_args(list, 'parent')

    # Parent does not take type arguments.
    with enough.raises(EnoughTypingErrors.NotGeneric(object)):
        enough.infer_type_args(list, object)

    # Child is not a subclass of parent.
    with enough.raises(
        EnoughTypingErrors.NotSubclass(child=Collection, parent=Sequence)
    ):
        enough.infer_type_args(Collection, Sequence)

    # Bad number of arguments.
    with enough.raises(EnoughTypingErrors.BadNumArgs(expected=2, actual=3)):
        enough.infer_type_args(dict[int, str, float], dict)

    # Test exceptional cases.
    # Inconsistent inheritance.
    class A(Sequence[int]): pass
    class B(Sequence[float]): pass
    class C(A, B): pass
    with enough.raises(
        EnoughTypingErrors.InconsistentInheritance(
            var='T1', example1=int, example2=float
        )
    ):
        enough.infer_type_args(C, Sequence)
