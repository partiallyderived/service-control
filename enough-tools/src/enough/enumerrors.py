from __future__ import annotations

import dataclasses
import typing
from collections import OrderedDict
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from enum import Enum, EnumMeta
from types import CodeType
from typing import Any, Final, Generic

from enough._exception import BRError
from enough.attrmap import AttrMap
from enough.types import Catchable, E, E2, T


class _EnumErrors(type, Generic[E]):
    # This class basically contains the implementation of EnumErrors. Having this be a separate class instead of putting
    # all this code in EnumErrors makes it so Enum properly treats this as a mix-in class so that the enumerated
    # exception types will have the methods defined here as class methods.

    # The compiled f-string.
    _compiled: CodeType

    #: Recognized attributes.
    attrs: frozenset[str]

    @classmethod
    def error_type(mcs) -> type[E]:
        """Get the exception type this was parameterized with.

        :return: Exception type this was parameterized with.
        """
        # Get the type arg this is parameterized with.
        # Avoid a circular import by handling these types specially.
        if mcs.__name__ == 'EnumErrorsErrors' or mcs.__name__ == 'BRTypingErrors':
            return BRError
        import enough.typing
        return typing.get_args(enough.typing.infer_type_args(mcs, EnumErrors))[0]

    def mro(cls=None) -> list[type]:
        # This needs to be defined since EnumMeta does not expect mixins to subclass type, and calls mro() without
        # parameters, leading to a TypeError. So, we need to be able to handle mro() with and without an argument.
        if cls is None:
            return type.mro(_EnumErrors)
        return type.mro(cls)

    def __new__(
        mcs, fmt: str, attrs: str | Iterable[str] = (), mixins: type[BaseException] | Iterable[type[BaseException]] = ()
    ) -> type[E]:
        """Create a new subclass of the parameterized exception type with the given format string,
        recognized attributes, and any :code:`BaseException` types to mix in.

        :param fmt: String which will be evaluated as an f-string to create the exception message from an instance of
        this :code:`Exception` The supplied keyword arguments and any methods available to instances of the resulting
        type may be used directly in this string without :code:`self` which should not be used.
        :param attrs: The keywords which are to be recognized by this subclass.
        :param mixins: Other types to mix in. May be a single type or an iterable of types.
        :return: The new exception type.
        :raise BRError: If any of the following are true:
            * No type argument was supplied to :class:`.EnumErrors`.
            * A type argument which was not a type was supplied to :class:`.EnumErrors`.
            * The type argument given to :class:`.EnumErrors` does not inherit from :code:`BaseException`.
        """
        type_arg = mcs.error_type()
        if not isinstance(type_arg, type):
            if type_arg is Any:
                raise EnumErrorsErrors.NoTypeArg(mcs)
            raise EnumErrorsErrors.NotType(type_arg)
        if not issubclass(type_arg, BaseException):
            raise EnumErrorsErrors.NotExcType(type_arg)
        if isinstance(attrs, str):
            attrs = frozenset({attrs})
        else:
            attrs = frozenset(attrs)
        if not isinstance(mixins, Iterable):
            mixins = mixins,
        typ = type.__new__(mcs, '', (type_arg,) + tuple(mixins), {})
        # Respect the order given in attrs.
        typ.__annotations__ = OrderedDict((attr, Any) for attr in attrs)
        if 'args' in attrs:
            # This allows attributes Exception.args to be repurposed. Otherwise, dataclass might complain that a
            # non-default attribute follows a default one, if there is another attribute after args.
            typ.args = dataclasses.MISSING
        typ = dataclasses.dataclass(typ)
        typ.attrs = frozenset(attrs)

        typ._compiled = compile(f'f{fmt!r}', '<string>', 'eval')
        typ._original_init = typ.__init__
        typ.__init__ = lambda *args, **kwargs: None

        def __str__(self) -> str:
            # Create new string method for instance.
            return eval(self._compiled, {}, AttrMap(self))

        typ.__str__ = __str__
        # Need this line to prevent EnumMeta from calling __new__ a second time in order to initialize the provided
        # arguments as the "value" of the enumerated exception.
        typ._value_ = fmt, attrs, mixins
        return typ

    def collect_errors(
        cls,
        args: Iterable[T],
        fn: Callable[[T], object],
        typ: Catchable,
        /,
        dest: str | None = 'errors',
        key_fn: Callable[[T], object] | None = None,
        **kwargs: object
    ) -> None:
        """Function which attempts to call :code:`fn` on every item in :code:`args`. For each argument :code:`arg` for
        which :code:`fn(arg)` results in an exception of type :code:`typ` being raised, a dictionary is updated with the
        key :code:`arg` set to the raised exception. After iteration is complete, if any exceptions of type :code:`typ`
        were raised, an exception of this type is raised instead, with the given keyword arguments and an additional
        keyword argument corresponding to :code:`dest` which has the dictionary as a value.

        :param args: Arguments to iterate over.
        :param fn: Function to call on each argument.
        :param typ: Type (or types) of exceptions to catch.
        :param dest: Name of attribute with which to set the error mapping. A value of :code:`None` will result in the
            mapping not being stored.
        :param key_fn: If supplied, use this function to determine the key in the resulting mapping for each argument
            instead of the argument itself.
        :param kwargs: Additional keyword arguments to construct the exception with.
        :raise E: If any exceptions of type :code:`typ` are raised during iteration.
        """
        errors = {}
        for arg in args:
            try:
                fn(arg)
            except typ as e:
                if key_fn is not None:
                    arg = key_fn(arg)
                errors[arg] = e
        if errors:
            if dest is not None:
                kwargs[dest] = errors
            raise cls(**kwargs)

    @contextmanager
    def wrap(cls, typ: EnumErrors[E2], forward: bool | Iterable[str] = True, **kwargs: object) -> None:
        """Context manager which, upon an exception inheriting from :code:`typ` being raised, instead raises an
        exception of this type, optionally inheriting some or all of the attributes from the raised type. Useful for
        keeping the behavior of another enum error but raising a different exception type.
        :param typ: Exception type to wrap. Must be an instance of :class:`.EnumErrors`.
        :param forward: If :code:`True`, forward all attributes from the caught exception to the raised exception. If
            :code:`False`, do not do any forwarding. If instead a collection is specified, all attributes from that
            collection will be forward and no others.
        :param kwargs: Additional keyword arguments to construct the exception with.
        :raise E: If a :code:`typ` is raised.
        """
        try:
            yield
        except typ as e:
            forwards = typ.attrs if forward is True else () if not forward else forward
            for attr in forwards:
                kwargs[attr] = getattr(e, attr)
            raise cls(**kwargs)

    @contextmanager
    def wrap_error(cls, typ: Catchable, /, dest: str | None = 'error', **kwargs: object) -> None:
        """Context manager which, upon an exception of type :code:`typ` being raised, instead raises an exception of
        constructed with the given keyword argument name :code:`dest` set to that error, and additional keyword
        arguments given by :code:`kwargs`.

        :param typ: Type (or types) of exception to catch.
        :param dest: Keyword argument with which to supply the wrapped error. A value of :code:`None` will result in the
            exception not being stored.
        :param kwargs: Additional keyword arguments to supply.
        :raise E: If an exception of type :code:`typ` is raised.
        """
        try:
            yield
        except typ as e:
            if dest is not None:
                kwargs[dest] = e
            raise cls(**kwargs)


class _EnumErrorsMeta(EnumMeta):
    # This metaclass alters the behavior of EnumMeta in 2 ways:
    # 1: __getitem__ is overridden for EnumMeta so that it uses __class_getitem__ instead of the default behavior. This
    #   allows the existence of an Enum class which also inherits from Generic without errors arising when type
    #   arguments are given to the Enum class (for instance, the default behavior for A[int] would be to look for an
    #   enum member named "int" rather than to given a type alias for A parameterized with int).
    # 2: __new__ is overridden so that names are added to each type (__name__ and __qualname__ are originally set to the
    #   empty string because the name of the type is not yet accessible at EnumErrors.__new__). Additionally, the
    #   monkey-patched __init__ (see EnumErrors.__new__) is overridden by the dataclass __init__).
    def __getitem__(cls, item: Any) -> Any:
        # noinspection PyUnresolvedReferences
        return cls.__class_getitem__(item)

    def __new__(mcs, name: str, bases: tuple[type, ...], dct: dict[str, object], **kwargs: Any) -> Enum:
        result = super().__new__(mcs, name, bases, dct, **kwargs)
        for typ in result:
            typ.__init__ = typ._original_init
            typ.__name__ = typ._name_
            typ.__qualname__ = f'{name}.{typ._name_}'
            typ.__str__.__qualname__ = f'{typ.__qualname__}.__str__'
            delattr(typ, '_original_init')
        return result


class EnumErrors(_EnumErrors[E], Enum, metaclass=_EnumErrorsMeta):
    """Subclass of :code:`Enum` for which all instances are exception *types* (not instances). Each enumerated value
    should be given a tuple of 1 to 3 values. The first value is an f-string which may use attributes of instantiated
    exceptions of that type as though they were local variables (i.e., if that exception type has an attribute called
    "data", this f-string can use {data} to interpolate a string representation of the data attribute). The second value
    is an iterable over strings which are the attributes to be recognized by the exception type. These attributes must
    be set in the __init__ method, which is the same as that for a :code:`dataclass` with those attributes. The third
    value may be either a type or an iterable of types to mix-in to the exception. Often, you may want to specify
    standard exception types to inherit from (like :code:`ValueError`). Each enumerated exception type will subclass
    the type parameter given to :class:`.EnumErrors`, for which a subtype of :code:`BaseException` must be supplied.
   """

    # Explicitly define __str__ and __repr__ to match those of type.
    def __str__(cls) -> str:
        return type.__str__(cls)

    def __repr__(cls) -> str:
        return type.__repr__(cls)


# Message to prefix all exception messages which occur in the course of creating a an EnumErrors instance.
_INIT_FAILED_PREFIX: Final[str] = 'Failed to create enumerated exception class:'


# Message accompanying errors involving the generic argument to not being a subclass of BaseException.
_TYPE_ERROR_HINT: Final[str] = (
    '(EnumErrors subclasses MUST supply a single concrete type parameter which is a subclass of BaseException)'
)


class EnumErrorsErrors(EnumErrors[BRError]):
    """Errors which occur when using the class :class:`.EnumErrors` itself. This class is *not* intended to be used by
    subclasses of :class:`.EnumErrors`.
    """
    NoTypeArg = (
        f'{_INIT_FAILED_PREFIX} {{type.__name__}} must supply a type argument to {EnumErrors.__name__} '
            f'{_TYPE_ERROR_HINT}',
        'type',
        TypeError
    )
    NotExcType = (
        f'{_INIT_FAILED_PREFIX} type argument "{{type.__name__}}" does not subclass BaseException {_TYPE_ERROR_HINT}',
        'type',
        TypeError
    )
    NotType = f'{_INIT_FAILED_PREFIX} type argument "{{obj}}" is not a type {_TYPE_ERROR_HINT}', 'obj', TypeError
