from __future__ import annotations

import typing
from collections import *
from collections.abc import *
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from types import EllipsisType, GenericAlias
from typing import _BaseGenericAlias, Any, Concatenate, Final, Generic, List, ParamSpec, TypeVar

from enough._exception import BRError
from enough.enumerrors import EnumErrors


class BRTypingErrors(EnumErrors[BRError]):
    """Exception types raised in bobbeyreese.typing."""
    BadNumArgs = (
        'Could not assign parameters: expected {expected} args, found {actual}.', ('expected', 'actual'), TypeError
    )
    ChildNotType = 'Argument for child ({child}) is not a type.', 'child', TypeError
    InconsistentInheritance = (
        'Inconsistent generic inheritance: conflicting type arguments for {var}: {example1}, {example2}',
        ('var', 'example1', 'example2'),
        TypeError
    )
    NotGeneric = 'Parent class {parent.__name__} does not take type arguments.', 'parent', TypeError
    NotSubclass = '{child.__name__} is not a subclass of {parent.__name__}.', ('child', 'parent'), TypeError
    ParentNotType = 'Argument for parent ({parent}) is not a type.', 'parent', TypeError


# These type variables will be used to given default generic inheritance for standard library generic types.
T1 = TypeVar('T1')
T2 = TypeVar('T2')
T3 = TypeVar('T3')
P = ParamSpec('P')
TP = TypeVar('TP')

# Type of a generic alias which includes both user-defined and standard library aliases.
GeneralAlias = _BaseGenericAlias | GenericAlias

# Type of a generic alias which has accepted type arguments, even if they are type variables.
ParameterizedAlias = type(List[int]) | GenericAlias

# Type of an entity which is either a type or a type alias.
TypeOrAlias = type[object] | GeneralAlias

# Any kind of type parameter, including TupleParam.
TypeVariable = TypeVar | ParamSpec
TypeVariables = Sequence[TypeVariable, ...]

# Type of a generic type. Of course, it includes types that are not generic.
GenericType = type[
    type |
    AbstractAsyncContextManager |
    AbstractContextManager |
    AsyncIterable |
    Awaitable |
    Callable |
    Container |
    Generic |
    Iterable
]

# Type of an entity that can (sanely) be used as a type argument for a TypeVar.
TypeVarArg = type[object] | GeneralAlias | TypeVar | type(Any)

# Type of an entity that can (sanely) be used as a type argument for ParamSpec.
ParamSpecArg = tuple[TypeVarArg, ...] | list[TypeVarArg] | EllipsisType | ParamSpec | type(Concatenate)

# Type of an entity that represents sane type arguments to supply to a tuple.
TupleParamArg = tuple[TypeVarArg, ...] | tuple[TypeVarArg, EllipsisType]

# Type of any type parameter argument.
TypeArg = TypeVarArg | ParamSpecArg | TupleParamArg
TypeArgs = tuple[TypeArg, ...]

# Type of a type parameter argument which has been processed (see the process function below).
ProcessedArg = TypeVarArg | ParamSpec | tuple[TypeVarArg | ParamSpec, ...]
ProcessedArgs = Sequence[ProcessedArg]

# Type of mapping from type variables to their assignments.
TypeAssignments = dict[TypeVariable, ProcessedArg]

# Dummy ParamSpec to use to simplify substitution.
_P = ParamSpec('_P')

# Implicit values to use as standard collection bases, which do not supply type arguments to their bases.
# noinspection PyTypeHints
IMPLICIT_BASES: dict[type[object], ParameterizedAlias | tuple[ParameterizedAlias, ...]] = {
    AbstractAsyncContextManager: Generic[T1],
    AbstractContextManager: Generic[T1],
    AsyncIterable: Generic[T1],
    AsyncIterator: AsyncIterable[T1],
    AsyncGenerator: (AsyncIterator[T1], Generic[T1, T2]),
    Awaitable: Generic[T1],
    Coroutine: (Awaitable[T3], Generic[T1, T2, T3]),
    Callable: Generic[P, T1],
    Container: Generic[T1],
    Iterable: Generic[T1],
    Reversible: Iterable[T1],
    Iterator: Iterable[T1],
    Generator: (Iterator[T1], Generic[T1, T2, T3]),
    enumerate: Iterator[tuple[int, T1]],
    Collection: (Container[T1], Iterable[T1]),
    ValuesView: Collection[T1],
    Sequence: (Collection[T1], Reversible[T1]),
    ByteString: Sequence[int],
    bytes: ByteString,
    memoryview: ByteString,
    range: Sequence[int],
    MutableSequence: Sequence[T1],
    UserList: MutableSequence[T1],
    bytearray: MutableSequence[int],
    deque: MutableSequence[T1],
    list: MutableSequence[T1],
    Set: Collection[T1],
    KeysView: Set[T1],
    ItemsView: Set[tuple[T1, T2]],
    frozenset: Set[T1],
    MutableSet: Set[T1],
    set: MutableSet[T1],
    Mapping: (Collection[T1], Generic[T1, T2]),
    MutableMapping: Mapping[T1, T2],
    ChainMap: MutableMapping[T1, T2],
    UserDict: MutableMapping[T1, T2],
    dict: MutableMapping[T1, T2],
    Counter: dict[T1, int],
    OrderedDict: dict[T1, T2],
    defaultdict: dict[T1, T2]
}

# Types whose assignments should be inherited from subclasses even if they don't appear in that class's mro (e.g., they
# are subclasses via a subclass hook).
HOOK_DEFAULTS: Final[tuple[TypeOrAlias, ...]] = ItemsView,


def all_vars(args: ProcessedArgs) -> TypeVariables:
    # Get all the unique parameters in order for each arg in args.
    seen = set()
    parameters = []
    for arg in args:
        for p in get_vars(arg):
            if p not in seen:
                seen.add(p)
                parameters.append(p)
    return tuple(parameters)


def apply(typ: GenericType, args: ProcessedArgs, vrs: TypeVariables) -> ParameterizedAlias:
    # Apply the given processed arguments to typ.
    # Prepare each argument so it is ready to be used in a type argument list.
    args = tuple(unprocess(arg) for arg in args)
    if typ is tuple:
        # noinspection PyTypeChecker
        return tuple[args[0]]
    return typ[tuple(prepare(arg, var) for arg, var in zip(args, vrs))]


def clean(args: tuple[TypeVarArg | ProcessedArg, ...]) -> ProcessedArg:
    # After substitution, arguments are "cleaned" so that they are a flattened tuple where there are no consecutive
    # occurrences of _P, which is a placeholder for ellipsis objects (see "_process" below).
    new_arg = []
    last_was_ellipsis = False
    for arg in args:
        if arg is _P:
            if last_was_ellipsis:
                continue
            last_was_ellipsis = True
            new_arg.append(_P)
        else:
            last_was_ellipsis = False
            if isinstance(arg, tuple):
                new_arg += arg
            else:
                new_arg.append(arg)
    return tuple(new_arg)


def ensure_tuple(arg: T1) -> T1 | tuple[T1]:
    # Ensure that the given argument is a tuple.
    return arg if isinstance(arg, tuple) else (arg,)


def get_vars(arg: ProcessedArg) -> tuple[TypeVariable, ...]:
    # Get all the type parameters appearing in arg in order.
    # To accomplish this, arg, which is a tuple, is expanded inside a Concatenate between two instances of _P.
    # The first instance of _P ensures that the first parameter found is _P, allowing us to easily ignore it, even if
    # it appears in arg.
    # The second instance of _P ensures that the argument list ends in ParamSpec, without which the Concatenation will
    # fail to be created. [1:] discards the _P parameter.
    return Concatenate[(_P, *ensure_tuple(arg), _P)].__parameters__[1:]


def has_args(typ: TypeOrAlias) -> bool:
    # Determine if the given argument is a generic type alias with arguments.
    # "isinstance(base, type(List))" tests if base is a "_SpecialGenericAlias", the type of type aliases for
    # builtin collections. In this case, we want to treat base as though no type arguments were given.
    return typing.get_origin(typ) is not None and not isinstance(typ, type(List))


def is_generic(typ: type[object]) -> bool:
    # Determine if the given type is generic and can take type arguments.
    if not isinstance(typ, type):
        raise BRTypingErrors.ParentNotType(parent=typ)
    # noinspection PyTypeHints
    return (
        typ is type
        or typ is tuple
        or (typ in IMPLICIT_BASES and bool(Assignments.get(typ).vars))
        or (issubclass(typ, Generic) and bool(getattr(typ, '__parameters__', ())))
    )


def join(src: TypeAssignments, dest: TypeAssignments) -> TypeAssignments:
    # Join assignments in dest into assignments for src.
    return src | {var: sub_map(src, arg) for var, arg in dest.items()}


def orig_bases(typ: type[object]) -> tuple[TypeOrAlias, ...]:
    # Get typ.__orig_bases__ if it gave type arguments to its parameters. Otherwise, get typ.__bases__ (note that
    # typ.__orig_bases__ will be those for the class which previously gave type arguments to bases in the mro if typ
    # did not give any itself).
    if (implicit := IMPLICIT_BASES.get(typ)) is not None:
        return ensure_tuple(implicit)
    # noinspection PyUnresolvedReferences
    if (
        hasattr(typ, '__orig_bases__') and not
        any(getattr(base, '__orig_bases__', ()) is typ.__orig_bases__ for base in typ.__bases__)
    ):
        bases = typ.__orig_bases__
    else:
        bases = typ.__bases__
    # noinspection PyArgumentList
    mro = set(typ.mro(typ) if issubclass(typ, type) else typ.mro())
    bases_to_add = []
    for hook_default in HOOK_DEFAULTS:
        origin = typing.get_origin(hook_default) or hook_default
        if origin not in mro and issubclass(typ, origin):
            bases_to_add.append(hook_default)
    return bases + tuple(bases_to_add)


def prepare(arg: TypeArgs, var: TypeVariable) -> TypeArg:
    # Depending on the type of var, prepare arg for parameterization of a type.
    return arg[0] if isinstance(var, TypeVar) or arg == (...,) else list(arg)


def _process(arg: TypeArg) -> ProcessedArg:
    # "Process" the given type parameter argument so that it is a ProcessedArg, a flatten tuple of type arguments of
    # which none are ellipses. This processing is done because a ProcessedArg can be easily expanded in Concatenate for
    # convenient substitution and detection of type parameters. It also allows us to treat all type parameter arguments
    # as the same up to the point before we actually need to substitute them in a type argument list.
    if typing.get_origin(arg) is Concatenate:
        return _process(typing.get_args(arg))
    if isinstance(arg, (list, tuple)):
        # Substitute all ellipses for _P and clean the resulting tuple.
        return clean(tuple(_P if a is ... else a for a in arg))
    if arg is ...:
        return _P
    # Otherwise, just return the original argument.
    return arg


def process(arg: TypeArg, proxies: dict[TypeVariable, TypeVariable]) -> ProcessedArg:
    # Process the given arguments. Calls _process, and then substitutes any type parameters in the processed value with
    # their corresponding proxies.
    processed = _process(arg)
    vrs = get_vars(processed)
    return sub(tuple(proxies.get(var, var) for var in vrs), processed)


def sub(args: ProcessedArgs, target: ProcessedArg) -> ProcessedArg:
    # Substitute the given arguments for the type parameters in target.
    # Like params above, this uses a trick of expanding the arguments inside Concatenate with a _P on both sides.
    # The first _P ensures that _P is the first parameter so that we do not have to determine its position, while the
    # second _P ensures that the type arguments end in a ParamSpec, which is a requirement for Concatenate before
    # substitution. [1:-1] discards the extraneous _Ps.
    if not args:
        return target
    result = clean(typing.get_args(Concatenate[(_P, *ensure_tuple(target), _P)][(_P, *args)])[1:-1])
    if not isinstance(target, tuple):
        return result[0]
    return result


def sub_map(assignments: TypeAssignments, target: ProcessedArg) -> ProcessedArg:
    # Like sub, but uses a mapping from variables to arguments and infers uses that to infer the order in which to pass
    # the arguments.
    return sub(tuple(assignments.get(var, var) for var in get_vars(target)), target)


def type_arg_split(typ: TypeOrAlias) -> tuple[type[object], TypeArgs | None]:
    # Split the given type or alias into the origin type and the type arguments, or None if there aren't any.
    origin = typing.get_origin(typ)
    if origin is None or isinstance(typ, type(List)):
        # noinspection PyTypeChecker
        return origin or typ, None
    return origin, typing.get_args(typ)


def unprocess(arg: ProcessedArg) -> TypeArgs:
    # Undo the processing logic (replace _P with ...) to prepare the argument for parameterization of a type.
    return typing.get_args(Concatenate[(*ensure_tuple(arg), _P)][...])[:-1]


def var_default(var: TypeVariable) -> ProcessedArg:
    # Get the default value for a type variable.
    return _P if isinstance(var, ParamSpec) else (Any, _P) if var is TP else Any


class Assignments:
    # Represents the type variable assignments for a particular type.
    # A cache is used for convenience and to ensure proxies are not created more than once for the same type.
    cache: Final[dict[TypeOrAlias, Assignments]] = {}

    # Mapping from assigned type variables to their assignments.
    args: TypeAssignments

    # Tuple of type variables that remain unassigned.
    vars: TypeVariables

    @staticmethod
    def from_bases(bases: tuple[TypeOrAlias, ...], proxies: OrderedDict[TypeVariable, TypeVariable],) -> Assignments:
        # Core logic for constructing assignments for a type.
        proxies = proxies or OrderedDict()
        # Start with Assignments object with no assignments and all unassigned variables.
        assignments = Assignments({}, tuple(proxies.values()))
        for base in bases:
            # Iterate over all origin bases.
            origin, args = type_arg_split(base)
            if origin is Generic:
                # Processing Generic would be problematic: it's just parameterized with the type parameters of origin.
                continue
            # If base has arguments, process them. Otherwise default them.
            base_assignments = (
                Assignments.get(origin).default() if args is None else Assignments.get(origin).process(args, proxies)
            )
            # Update the assignments from the base class.
            assignments.update(base_assignments)
        return assignments

    @staticmethod
    def from_tuple_args(args: TypeArgs) -> Assignments:
        # Create an Assignments instance from tuple arguments.
        args = tuple(process(arg, OrderedDict()) for arg in args)
        new_args = {TP: args}
        if len(args) == 1 or (len(args) == 2 and args[1] is _P):
            new_args |= Assignments.get(Sequence[new_args[TP][0]]).args
        return Assignments(new_args, all_vars(args))

    @staticmethod
    def from_type_or_alias(typ: TypeOrAlias) -> Assignments:
        # Get an Assignments instance from a type or a type alias.
        origin, args = type_arg_split(typ)
        if origin is tuple:
            if args is None:
                return Assignments({}, (TP,))
            return Assignments.from_tuple_args(args)
        if args is None:
            bases = orig_bases(origin)
            for base in bases:
                if typing.get_origin(base) is Generic:
                    params = base.__parameters__
                    break
            else:
                params = all_vars(bases)
            proxies = OrderedDict((p, type(p)(p.__name__)) for p in params)
            return Assignments.from_bases(bases, proxies)
        return Assignments.get(origin).process(args, OrderedDict())

    @staticmethod
    def get(typ: TypeOrAlias) -> Assignments:
        # Get the Assignments object for the given type.
        if typ in Assignments.cache:
            return Assignments.cache[typ]
        return Assignments.cache.setdefault(typ, Assignments.from_type_or_alias(typ))

    def __init__(self, args: TypeAssignments | None = None, vrs: TypeVariables = ()) -> None:
        self.args = args or {}
        self.vars = vrs

    def apply(self, typ: GenericType) -> ParameterizedAlias:
        # Apply these assignments to the given type.
        if self.vars:
            # Default any unset variables before applying.
            return self.default().apply(typ)
        # Get assignments for typ.
        assignments = Assignments.get(typ)
        # It might seem like var.kind.default() is unnecessary assuming self corresponds to assignments for a subclass
        # of typ. However, it could be a subclass due to __subclasshook__, so use var.kind.default() in case this is
        # true.
        return apply(typ, tuple(self.args.get(var, var_default(var)) for var in assignments.vars), assignments.vars)

    def assign(self, args: ProcessedArgs) -> Assignments:
        # Return a new Assignments object which is the result of assigning each variable in self to args, in order.
        if self.is_tuple():
            if len(args) == 1 and isinstance(args[0], tuple):
                args = args[0]
            return Assignments.get(tuple[args])
        if len(args) != len(self.vars):
            raise BRTypingErrors.BadNumArgs(expected=len(self.vars), actual=len(args))
        if not args:
            return self
        return Assignments(join(dict(zip(self.vars, args)), self.args), all_vars(args))

    def default(self) -> Assignments:
        # Return a new Assignments object with all unset variables defaulted.
        if not self.vars:
            return self
        return self.assign(tuple(var_default(var) for var in self.vars))

    def is_tuple(self) -> bool:
        # Determine whether this Assignments instance is for a tuple.
        return len(self.vars) == 1 and self.vars[0] is TP

    def process(self, args: TypeArgs, proxies: OrderedDict[TypeVariable, TypeVariable]) -> Assignments:
        # Process the given raw arguments.
        return self.assign(tuple(process(arg, proxies) for arg in args))

    def update(self, other: Assignments) -> None:
        # Update our assignments with the assignments in other and check their consistency.
        self.args = join(other.args, self.args)
        for var, arg in other.args.items():
            if self.args[var] != other.args[var]:
                raise BRTypingErrors.InconsistentInheritance(var=var.__name__, example1=self.args[var], example2=arg)


def infer_type_args(child: TypeOrAlias, parent: GenericType) -> ParameterizedAlias:
    """Return a parameterized alias whose type assignments are inferrable from :code:`child`.

    :param child: Type or alias to infer type arguments from.
    :param parent: Generic type to infer type arguments for.
    :return: The resulting alias.
    :raise BRError: If any of the following are true:
        * Either :code:`parent` or the origin of :code:`child` or  are not types.
        * The origin of :code:`child` does not subclass :code:`parent`
        * :code:`parent` is not a generic type,
        * The generic type hierarchy of :code:`child` or :code:`parent` contains inconsistencies
            (like inheriting from both :code:`Sequence[int]` and :code:`Sequence[str]`, for example)
        * Any class in the generic type hierarchies supplies more than the expected number of type arguments to a base,
            such as, for instance, inheriting from :code:`Sequence[int, str]`.
    """
    origin = typing.get_origin(child) or child
    if not is_generic(parent):
        raise BRTypingErrors.NotGeneric(parent=parent)
    if parent is type:
        return type[child]
    if not isinstance(origin, type):
        raise BRTypingErrors.ChildNotType(child=origin)
    if not issubclass(origin, parent):
        raise BRTypingErrors.NotSubclass(child=child, parent=parent)
    # Get all the variable assignments for child and apply them to parent.
    return Assignments.get(child).apply(parent)
