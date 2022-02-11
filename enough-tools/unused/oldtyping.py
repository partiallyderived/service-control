from __future__ import annotations

import typing
from collections import *
from collections.abc import *
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from enum import Enum
from types import EllipsisType, GenericAlias
from typing import (
    _BaseGenericAlias, _GenericAlias, Any, Concatenate, Final, Generic, ParamSpec, Protocol, Tuple, TypeVar
)

from ordered_set import OrderedSet

from bobbeyreese.kwerror import ErrorContext, KWError

class BRTypingError(KWError):
    """Base class of exceptions raised in bobbeyreese.typing."""

class BRTypingContext(ErrorContext[BRTypingError], Enum):
    """Context for :class:`.BRTypingError`."""
    BAD_NUM_ARGS = 'Could not assign parameters: expected {expected} args, found {actual}.', ('expected', 'actual')
    CHILD_NOT_TYPE = 'Argument for child ({child}) is not a type.', ('child',)
    INCONSISTENT_INHERITANCE = (
        'Inconsistent generic inheritance: {origin.__name__} has conflicting type arguments for {var.__name__}:'
        '{example1}, {example2}',
        ('origin', 'var', 'example1', 'example2')
    )
    INCONSISTENT_TUPLE_INHERITANCE = (
        'Inconsistent tuple type arguments: {origin.__name__} inherits from both {example1} and {example2}.',
        ('origin', 'example1', 'example2')
    )
    NOT_GENERIC = 'Parent class {parent.__name__} does not take type arguments.', ('parent',)
    NOT_SUBCLASS = '{child.__name__} is not a subclass of {parent.__name__}.', ('child', 'parent')
    PARENT_NOT_TYPE = 'Argument for parent ({parent}) is not a type.', ('parent',)

# The following TypeVars are defined as aesthetically pleasing/intuitive names to give as "default" type vars for
# standard library generic types.

# Type variable for an element of iterables. Also yield type for generators.
E = TypeVar('E')

# Value type var for maps.
V = TypeVar('V')

# Return type for Callable.
R = TypeVar('R')

# Type variable for elements of a Container. Usually, E is used instead since most containers are iterable.
C = TypeVar('C')

# ParamSpec to use for Callable.
P = ParamSpec('P')

# Key for ItemsView.
IK = TypeVar('IK')

# Value for ItemsView.
IV = TypeVar('IV')

# Generator vars.

# Send type.
GS = TypeVar('GS')

# Return type.
GR = TypeVar('GR')

# Async vars.

# Type variable for elements of async iterables. Also yield type for async generators.
A = TypeVar('A')

# Send type for async generators.
AS = TypeVar('AS')

# Coroutine vars.

# Yield type.
CY = TypeVar('CY')

# Send type.
CS = TypeVar('CS')

# Return type (also used for Awaitable).
CR = TypeVar('CR')

# Context manager vars.

# Normal.
CM = TypeVar('CM')

# Async.
AM = TypeVar('AM')

#: Type of a generic alias which includes both user-defined and standard library aliases.
GeneralAlias = _BaseGenericAlias | GenericAlias

#: Type of a generic alias which has accepted type arguments, even if they are type variables.
ParameterizedAlias = _GenericAlias | GenericAlias

#: Type of a generic type available in the Python standard library. Does not include Generic.
StdGenericType = type[
    type |
    AbstractAsyncContextManager |
    AbstractContextManager |
    AsyncIterable |
    Awaitable |
    Callable |
    Container |
    Iterable
]

#: Type of a Generic type, excluding aliases.
# noinspection PyUnresolvedReferences
GenericType = Generic | StdGenericType

#: Type of any type parameter.
TypeParam = ParamSpec | TypeVar

#: Type of an entity that can (sanely) be used as a type argument for a TypeVar.
TypeArg = type[object] | type(Any) | GeneralAlias | TypeVar

#: Type of an entity that can (sanely) be used a ParamSpec argument.
ParamSpecArg = tuple[TypeArg, ...] | list[TypeArg] | type(Concatenate) | EllipsisType | ParamSpec

#: Type of any type parameter argument.
ParamArg = ParamSpecArg | TypeArg

#: Type of an entity which is either a type or a type alias.
TypeOrAlias = type[object] | GeneralAlias

#: Type of the argument to a ParamSpec argument as it appears in TypeAssignments. These values are essentially the same
#: as though they appeared in Concatenate, but these are more convenient to work with.
AssignedParamSpecArg = list[TypeArg | ParamSpec] | EllipsisType

#: Type of an argument assigned to any parameter in TypeAssignments.
AssignedArg = AssignedParamSpecArg | TypeArg

# Mapping from standard generic classes to the type parameters they will implicitly have by default.
DEFAULT_VARS: Final[dict[StdGenericType, tuple[TypeParam, ...]]] = {
    AbstractAsyncContextManager: (AM,),
    AbstractContextManager: (CM,),
    AsyncGenerator: (A, AS),
    AsyncIterable: (A,),
    AsyncIterator: (A,),
    Awaitable: (CR,),
    Callable: (P, R),
    ChainMap: (E, V),
    Collection: (E,),
    Container: (C,),
    Coroutine: (CY, CS, CR),
    Counter: (E,),
    ItemsView: (IK, IV),
    Iterable: (E,),
    Iterator: (E,),
    Generator: (E, GS, GR),
    KeysView: (E,),
    Mapping: (E, V),
    MutableMapping: (E, V),
    MutableSequence: (E,),
    MutableSet: (E,),
    OrderedDict: (E, V),
    Reversible: (E,),
    Sequence: (E,),
    Set: (E,),
    UserDict: (E, V),
    UserList: (E,),
    ValuesView: (E,),
    defaultdict: (E, V),
    deque: (E,),
    dict: (E, V),
    frozenset: (E,),
    list: (E,),
    set: (E,),
    tuple: ()
}

#: Mapping from standard library classes to the type parameter assignments they have implicitly by default.
DEFAULT_ARGS: Final[dict[type[object], dict[TypeParam, ParamArg]]] = {
    ByteString: {E: int},
    Counter: {V: int},
    ItemsView: {E: tuple[IK, IV]},
    bytearray: {E: int},
    bytes: {E: int},
    memoryview: {E: int},
    range: {E: int},
    type: {R: object}
}

class TypeAssignments:
    cache: Final[dict[TypeOrAlias, TypeAssignments]] = {}
    proxy_to_var: Final[dict[TypeParam, TypeParam]] = {}

    #: Mapping from type parameters to their assigned arguments, which may themselves be or contain type parameters.
    args: dict[TypeParam, AssignedArg]

    #: Tuple of free parameters which have not been given a value yet.
    vars: tuple[TypeParam, ...]

    #: The tuple arguments for this assignment, if any. None signifies no type arguments.
    tuple_args: tuple[TypeArg | EllipsisType, ...] | None

    #: Alias or type for which these are assignments for.
    typ: TypeOrAlias | None

    @staticmethod
    def _from_type(origin: type[object]) -> TypeAssignments:
        # Core logic for constructing a new type assignments object. Steps are as follows:
        # 1: Create "proxy" type parameters for all type parameters for origin. These type parameters have the same
        #    name, but are different objects. This gives them a unique identity as a parameter specifically for origin.
        #    This prevents assignment conflicts from occurring when the same type parameter appears for the parameters
        #    in multiple classes.
        # 2: Iterate over each original base of origin, each of which may be an alias. While iterating, substitute all
        #    appearances of parameters for origin in the type arguments given to bases with their proxy parameters.
        # 3: Assign the proxied type arguments to the assignments of each base via TypeAssignments.assign.
        # 4: Call TypeAssignments.update to inherit any type parameter assignments from that base and check for any
        #    inconsistencies.
        # 5: Repeat for the remaining bases.
        proxies = TypeAssignments.proxies(origin)
        assignments = TypeAssignments({}, tuple(proxies.values()), typ=origin)
        for base in orig_bases(origin):
            base_origin = typing.get_origin(base)
            if base_origin is None:
                base_origin = base
                base_args = None
            else:
                base_args = typing.get_args(base)
            if base_origin is Generic or base_origin is Protocol:
                continue
            other = TypeAssignments.get(base_origin)
            if base_args is None:
                other = other.defaulted()
            else:
                if base_origin is tuple:
                    base_args = tuple(sub_for_type_var(proxies, arg) for arg in base_args)
                else:
                    subbed = sub_for_all(proxies, dict(zip(other.vars, base_args)))
                    base_args = tuple(subbed[var] for var in other.vars)
                other = other.assign(base_args)
            assignments.update(other)
        return assignments

    @staticmethod
    def from_type(origin: type[object]) -> TypeAssignments:
        # Construct a type assignments object from a type.
        if origin in DEFAULT_VARS:
            assignments = TypeAssignments({}, DEFAULT_VARS[origin], typ=origin)
            if issubclass(origin, Collection):
                # Allows subclasses of origin to implicitly inherit it's default assignment for C.
                assignments.args[C] = E
        else:
            assignments = TypeAssignments._from_type(origin)
            if issubclass(origin, ItemsView) and E not in assignments.args:
                # Allows implicit ItemsView subclasses to infer more a more specific type argument for Iterables.
                assignments.args[E] = tuple[Any, Any]
        if origin in DEFAULT_ARGS:
            assignments.args.update(DEFAULT_ARGS[origin])
        return assignments

    @staticmethod
    def from_type_or_alias(typ: TypeOrAlias) -> TypeAssignments:
        # Construct a type assignments object from a type or a generic alias.
        origin = typing.get_origin(typ)
        if origin is None:
            return TypeAssignments.from_type(typ)
        args = typing.get_args(typ)
        if origin is tuple:
            if typ is Tuple:
                # Ambiguous because () are valid args for tuple, but
                # typing.get_args(x) is () for x in {tuple, tuple[()], Tuple, Tuple[()]}.
                # This means, since origin is not None for Tuple, we would otherwise incorrectly infer the given
                # arguments to be () in this case.
                return TypeAssignments.get(tuple)
            if len(args) == 1 or (len(args) == 2 and args[1] is ...):
                # Implicitly deduce iterator argument for tuple if it is a tuple or only one object or a tuple of
                # uniform type.
                return TypeAssignments({E: args[0]}, (), args, typ=tuple[args])
            return TypeAssignments({}, (), args, typ=tuple[args])
        origin_assignments = TypeAssignments.get(origin)
        # Need this check for aliases like List, Dict, etc. where origin may not be None even without type parameters.
        if args:
            return origin_assignments.assign(args)
        return origin_assignments

    @staticmethod
    def get(typ: type[object] | GeneralAlias) -> TypeAssignments:
        # Get the assignments for the given type. First checks the cache for the assignments, and if they could not be
        # found, computes and caches the assignments.
        if typ in TypeAssignments.cache:
            return TypeAssignments.cache[typ]
        assignments = TypeAssignments.from_type_or_alias(typ)
        assignments.typ = typ
        return TypeAssignments.cache.setdefault(typ, assignments)

    @staticmethod
    def proxies(origin: type[object]) -> OrderedDict[TypeParam, TypeParam]:
        # Computes a mapping from the original parameters in origin to their proxies.
        params = getattr(origin, '__parameters__', ())
        return OrderedDict((var, type(var)(var.__name__)) for var in params)

    def __init__(
        self,
        args: dict[TypeParam, AssignedArg] | None = None,
        params: tuple[TypeParam, ...] | None = None,
        tuple_args: tuple[TypeArg | EllipsisType, ...] | None = None,
        typ: TypeOrAlias | None = None
    ) -> None:
        self.args = args or {}
        self.vars = params or ()
        self.tuple_args = tuple_args
        self.typ = typ

    def apply(self, typ: GenericType) -> ParameterizedAlias:
        # Applies these type assignments to the given type, which should be a (not necessarily strict) superclass of
        # the type or alias origin these type assignments are for.
        if self.vars:
            # Default our type vars if we have any.
            return self.assign(default_args(self.vars)).apply(typ)
        if typ is tuple:
            if self.tuple_args is None:
                # noinspection PyTypeChecker
                return tuple[Any, ...]
            # noinspection PyTypeChecker
            return tuple[self.tuple_args]
        assignments = self.get(typ)
        # Sub back in original type parameters.
        args = tuple(self.args.get(var, default_arg(var)) for var in assignments.vars)
        return typ[args]

    def assign(self, args: tuple[ParamArg, ...]) -> TypeAssignments:
        # Assigns the given type arguments to these assignments, resulting in all parameters in self.vars being moved to
        # self.args with an assigned value and the type parameters appearing in args becoming the new free parameters
        # for self.vars.
        if self.typ is tuple:
            new_vars = tuple(OrderedSet(get_vars_for_type_var_arg(arg) for arg in args))
            return TypeAssignments({}, new_vars, args, typ=tuple[args])
        if len(args) != len(self.vars):
            raise BRTypingContext.BAD_NUM_ARGS(expected=len(self.vars), actual=len(args))
        elif not self.vars:
            return self
        var_to_arg = OrderedDict(zip(self.vars, args))
        new_args = sub_for_all(var_to_arg, self.args) | dict(var_to_arg)
        new_vars = get_all_vars(var_to_arg)
        new_tuple_args = (
            tuple(sub_for_type_var(var_to_arg, arg) for arg in self.tuple_args) if self.tuple_args else self.tuple_args
        )

        return TypeAssignments(new_args, new_vars, new_tuple_args, typ=self.typ[args])

    def defaulted(self) -> TypeAssignments:
        # Give default values to each remaining variable.
        if self.typ is tuple:
            return self.assign((Any, ...))
        return self.assign(default_args(self.vars))

    def update(self, other: TypeAssignments) -> None:
        # Inherit all type parameter assignments appearing in other. Raise a TypeError is there are any inconsistencies.
        # This function will never affect self.vars or mutate other.
        for var in self.args.keys() & other.args.keys():
            value1 = self.args[var]
            value2 = other.args[var]
            if value1 != value2:
                raise BRTypingContext.INCONSISTENT_INHERITANCE(
                    origin=typing.get_origin(self.typ) or self.typ, var=var, example1=value1, example2=value2
                )
        self.args.update(other.args)
        if self.tuple_args is not None and other.tuple_args is not None and self.tuple_args != other.tuple_args:
            raise BRTypingContext.INCONSISTENT_TUPLE_INHERITANCE(
                origin=typing.get_origin(self.typ) or self.typ,
                example1=tuple[self.tuple_args],
                example2=tuple[other.tuple_args]
            )
        self.tuple_args = self.tuple_args if self.tuple_args is not None else other.tuple_args

def default_arg(var: TypeParam) -> type(Any) | EllipsisType:
    # Get the default argument for the given type parameter (Any for TypeVars, ... for ParamSpecs).
    return Any if isinstance(var, TypeVar) else ...

def default_args(params: tuple[TypeParam, ...]) -> tuple[type(Any) | EllipsisType]:
    # default_args for a tuple of type parameters.
    return tuple(default_arg(var) for var in params)

def get_all_vars(var_to_arg: OrderedDict[TypeParam, AssignedArg]) -> tuple[TypeParam, ...]:
    # Get all the unique type parameters appearing in the arguments of var_to_arg in order.
    seen = set()
    params = []
    for var, arg in var_to_arg.items():
        new_vars = get_vars_for_arg(var, arg)
        [params.append(v) for v in new_vars if v not in seen]
        seen.update(new_vars)
    return tuple(params)

def get_vars_for_arg(var: TypeParam, arg: AssignedArg) -> tuple[TypeParam, ...]:
    # Get all the unique type parameters appearing in arg in order.
    if isinstance(var, TypeVar):
        return get_vars_for_type_var_arg(arg)
    elif isinstance(var, ParamSpec):
        return get_vars_for_param_spec_arg(arg)
    raise AssertionError('Expected only TypeVars or ParamSpecs.')

def get_vars_for_type_var_arg(arg: TypeArg) -> tuple[TypeVar, ...]:
    # Get all the unique TypeVars appearing in TypeVar argument arg in order.
    if isinstance(arg, TypeVar):
        return arg,
    return getattr(arg, '__parameters__', ())

def get_vars_for_param_spec_arg(arg: AssignedParamSpecArg) -> tuple[TypeParam, ...]:
    # Get all the unique type parameters appearing in the ParamSpec argument arg in order.
    if arg is ...:
        return ()
    seen = set()
    params = []
    for component in arg:
        if isinstance(component, ParamSpec):
            new_vars = (component,)
        else:
            new_vars = get_vars_for_type_var_arg(component)
        [params.append(var) for var in new_vars if var not in seen]
        # noinspection PyTypeChecker
        seen.update(new_vars)
    return tuple(params)

def is_generic(typ: type[object]) -> bool:
    # noinspection PyTypeHints
    return typ is type or typ in DEFAULT_VARS or (issubclass(typ, Generic) and bool(getattr(typ, '__parameters__', ())))

def orig_bases(typ: type[object]) -> tuple[TypeOrAlias, ...]:
    # Get typ.__orig_bases__ if it gave type arguments to its parameters. Otherwise, get typ.__bases__ (note that
    # typ.__orig_bases__ will be those for the class which previously gave type arguments to bases in the mro if typ
    # did not give any itself).
    # noinspection PyUnresolvedReferences
    if (
        hasattr(typ, '__orig_bases__') and not
    any(getattr(base, '__orig_bases__', ()) is typ.__orig_bases__ for base in typ.__bases__)
    ):
        return typ.__orig_bases__
    # noinspection PyTypeChecker
    return typ.__bases__

def sub_for_all(
    var_to_arg: dict[TypeParam, AssignedArg], old_values: dict[TypeParam, ParamArg]
) -> dict[TypeParam, AssignedArg]:
    # Return the mapping with the same keys as old_values but with any type parameters in the values of old_values
    # substituted with their value in var_to_arg, if it exists.
    return {var: sub_for_var(var_to_arg, var, old_value) for var, old_value in old_values.items()}

def sub_for_var(var_to_arg: dict[TypeParam, AssignedArg], var: TypeParam, old_value: ParamArg) -> AssignedArg:
    # Substitute any type parameters in old_value with their assigned argument in var_to_arg, if it exists. How the
    # substitution occurs depends on rather the argument is for a TypeVar or a ParamSpec.
    if isinstance(var, TypeVar):
        return sub_for_type_var(var_to_arg, old_value)
    elif isinstance(var, ParamSpec):
        return sub_for_param_spec(var_to_arg, old_value)
    raise AssertionError('Expected only TypeVars or ParamSpecs.')

def sub_for_type_var(var_to_arg: dict[TypeParam, AssignedArg], old_value: TypeArg) -> TypeArg:
    # Substitute any TypeVars in old_value with their assigned argument in var_to_arg, if it exists.
    if isinstance(old_value, TypeVar):
        return var_to_arg.get(old_value, old_value)
    params = getattr(old_value, '__parameters__', ())
    if params:
        return old_value[tuple(var_to_arg.get(param, param) for param in params)]
    return old_value

def sub_for_param_spec(var_to_arg: dict[TypeParam, AssignedArg], old_value: ParamSpecArg) -> AssignedParamSpecArg:
    # Substitute any ParamSpecs in old_value with their assigned argument in var_to_arg, if it exists.
    # This is substantially more complicated than sub_for_type_var.
    if old_value is ...:
        return ...
    if isinstance(old_value, ParamSpec):
        return var_to_arg.get(old_value, old_value)
    if typing.get_origin(old_value) is Concatenate:
        return sub_for_param_spec(var_to_arg, typing.get_args(old_value))
    new_arg = []
    last_was_ellipsis = False
    # At this point, we can assume old_value is either a tuple or a list.
    # Use a deque to flatten the ParamSpec arguments as we go by appending collections to the left of components in
    # reverse order.
    components = deque(old_value)
    while components:
        component = components.popleft()
        if component == ():
            # Skip empty parameter lists.
            continue
        if isinstance(component, ParamSpec):
            if component in var_to_arg:
                component = var_to_arg[component]
                if isinstance(component, ParamSpec):
                    new_arg.append(component)
                elif isinstance(component, (tuple, list)):
                    # Process the arguments in these collections from left to right. To accomplish this, we need to
                    # append left in reverse order.
                    [components.appendleft(x) for x in reversed(component)]
                else:
                    components.appendleft(component)
            else:
                new_arg.append(component)
        else:
            if component is ...:
                # Merge all ellipsis objects into a single ellipsis when they appear continuously.
                if not last_was_ellipsis:
                    new_arg.append(...)
                    last_was_ellipsis = True
            else:
                new_arg.append(sub_for_type_var(var_to_arg, component))
                last_was_ellipsis = False
    return new_arg

def infer_type_args(child: TypeOrAlias, parent: GenericType) -> ParameterizedAlias:
    # Given that child or its origin is a subclass of a generic type parent, return a parameterized alias of parent
    # with all type parameters substituted with the values that child has for them. All unset TypeVars default to Any,
    # all unset ParamSpecs default to ..., and if applicable, tuple arguments default to (Any, ...).
    origin = typing.get_origin(child) or child
    if not isinstance(origin, type):
        raise BRTypingContext.CHILD_NOT_TYPE(child=origin)
    if not isinstance(parent, type):
        raise BRTypingContext.PARENT_NOT_TYPE(parent=parent)
    # noinspection PyTypeChecker
    if not is_generic(parent):
        raise BRTypingContext.NOT_GENERIC(parent=parent)
    if parent is type:
        # Special case: the type parameter for type is the origin of child itself.
        return type[origin]
    if not issubclass(origin, parent):
        raise BRTypingContext.NOT_SUBCLASS(child=origin, parent=parent)
    return TypeAssignments.get(child).apply(parent)
