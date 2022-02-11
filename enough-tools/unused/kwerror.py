from __future__ import annotations

import typing
from collections import ChainMap
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, EnumMeta
from types import CodeType
from typing import Any, ClassVar, Final, Generic, NoReturn, TypeVar

from ordered_set import OrderedSet

from bobbeyreese.types import Catchable, T


class KWError(Exception):
    """Exception type which uses an underlying :class:`.ErrorContext` to distinguish between different parts of code
    where the exception is raised. This allows the caller catching :code:`KWErrors` to know precisely where the
    exception was raised without having to define an exception for every use case or decipher the exception message.
    Notice that the representation and definition of :code:`KWErrors`, including the formatted message, are separated
    from the code which raise them: this allows the entire specification of the exception to be organized in one
    location, allowing easy modification of the exception without having to look for where it was raised, and the code
    which raises the exception is much less cluttered without the exception message and only needs to specified the
    exception data. Additionally, an :code:`ErrorContext` instance specifies what data are allowed to be set on the
    :code:`KWError` instance to prevent accidental misuse. :code:`KWErrors` are immutable after creation.
    """

    #: Set of attributes which may not be accessed for this class unless they are given as keyword arguments upon
    #: initialization. Useful to override to suppress keys usually present in exception mixins like :code:`ImportError`.
    _NOT_ATTR: ClassVar[frozenset[str]] = frozenset({'_kwargs', '_msg', 'args'})

    #: The underlying keyword-arguments. Always includes the key :code:`ctx`.
    _kwargs: dict[str, object]

    #: The underlying exception message.
    _msg: str

    def __init__(self, ctx: _KWErrors[KWE], **kwargs: object) -> None:
        """Initialize this error.

        :param ctx: Context to use for the error.
        :param kwargs: Keyword arguments representing the data associated with the exception. Must included every key
            in :code:`ctx.attrs` and only those keys.
        :raise KWErrorError: If there are any missing or unrecognized arguments, or if :code:`ctx` is not parameterized
            with the type of this error.
        """
        if ctx.error_type() != type(self):
            raise KWErrorErrors.ERR_MISMATCH(actual=ctx.error_type(), context=ctx, expected=type(self))
        missing = {a for a in ctx.attrs if a not in kwargs}
        if missing:
            raise KWErrorErrors.MISSING_ATTRS(context=ctx, missing=missing)
        unrecognized = {k for k in kwargs if k not in ctx.attrs}
        if unrecognized:
            raise KWErrorErrors.UNRECOGNIZED_ATTRS(context=ctx, unrecognized=unrecognized)
        kwargs |= {'ctx': ctx}
        super().__setattr__('_kwargs', kwargs)
        super().__setattr__('_msg', eval(self.ctx.compiled, globals(), ChainMap(kwargs, self)))

    def __eq__(self, other: object) -> bool:
        """Test if :code:`self` == :code:`other`.

        :param other: Object to test equality for.
        :return: :code:`True` if :code:`self` and :code:`other` have the same data, :code:`False` otherwise.
        """
        if not isinstance(other, KWError):
            return False
        return super().__getattribute__('_kwargs') == object.__getattribute__(other, '_kwargs')

    def __getattribute__(self, name: str) -> object:
        """:code:`__getattribute__` override which disallows getting of attributes other than :code:`'ctx'` and those
        found in :code:`self.ctx.attrs`.

        :param name: Name of the attribute to get.
        :return: Value of the attribute.
        :raise AttributeError: If :code:`name` is not :code:`ctx` and :code:`name not in self.ctx.attrs`.
        """
        try:
            return super().__getattribute__('_kwargs')[name]
        except KeyError:
            if name in self._NOT_ATTR:
                # Trying to get these attributes will be considered an error if they are not present as keys in _kwargs.
                raise AttributeError(name)
            # Might be trying to get a bound method: defer to object.
            return super().__getattribute__(name)

    def __getitem__(self, key: str) -> object:
        """Same as `__getattribute__`, except it raises a :code:`KeyError` for a missing key rather than an
        :code:`AttributeError`. Used to allow the usage of the instance variables of :code:`self` in hte evaluation of
        f-strings.

        :param key: Attribute to get.
        :return: Value for :code:`key`.
        :raise KeyError: If :code:`key` is not an attribute for :code:`self`.
        """
        try:
            return self.__getattribute__(key)
        except AttributeError:
            raise KeyError(key)

    def __setattr__(self, name: str, value: object) -> NoReturn:
        """:code:`__setattr__` override which forbids modifications to :code:`self`, always raising an exception.

        :param name: Name of the attribute to try to set.
        :param value: Value to try to set the attribute to.
        :raise KWErrorError: Always.
        """
        raise KWErrorErrors.MODIFICATION()

    def __str__(self) -> str:
        """Construct the formatted exception message by using the compiled f-string in :code:`ctx`.

        :return: The formatted error message.
        """
        return super().__getattribute__('_msg')

    def __repr__(self) -> str:
        """Construct a string representation of this similar to how dataclasses are represented.

        :return: Name of the exception class followed by a parenthetical enclosure of the name of its configured
            :class:`.ErrorContext` and all supplied keyword arguments as :code:`key=value` strings.
        """
        kwargs = super().__getattribute__('_kwargs')
        parenthetical = ', '.join([self.ctx.name] + [f'{a}={kwargs[a]}' for a in self.ctx.attrs])
        return f'{type(self).__name__}({parenthetical})'


KWE = TypeVar('KWE', bound=KWError, covariant=True)
KWE2 = TypeVar('KWE2', bound=KWError)


class _KWError:
    # Compiled format string.
    _compiled: ClassVar[CodeType]

    def __getitem__(self, item: Any) -> Any:
        return getattr(self, item)

    def __str__(self) -> str:
        return eval(self._compiled, globals(), self)


class _KWErrorsMeta(type[KWE], Generic[KWE]):
    # The compiled f-string.
    _compiled: CodeType

    def error_type(cls) -> type[KWE]:
        """Get the exception type this context was parameterized with.

        :return: Exception type this context was parameterized with.
        """
        # Get the type arg this is parameterized with and raise an exception if is it not a subclass of KWError.
        import bobbeyreese.typing
        return typing.get_args(bobbeyreese.typing.infer_type_args(cls, _KWErrorsMeta))[0]

    def mro(cls=None) -> list[type]:
        # This needs to be defined since EnumMeta does not expect mixins to subclass type, and calls mro() without
        # parameters, leading to a TypeError. So, we need to be able to handle mro() with and without an argument.
        if cls is None:
            return type.mro(_KWErrorsMeta)
        return type.mro(cls)

    def __new__(
        mcs, fmt: str, attrs: Iterable[str] = (), mixins: Iterable[type[BaseException]] = ()
    ) -> _KWErrorsMeta[KWE]:
        """Create a new subclass of :code:`KWE` with the given format string, recognized keywords, and any
        :code:`BaseException` types to mix in.

        :param fmt: String which will be evaluated as an f-string to create the exception message from an instance of
        this :code:`Exception` The supplied keyword arguments and any methods available to instances of the resulting
        type may be used directly in this string without :code:`self` which should not be used.
        :param attrs: The keywords which are to be recognized by this subclass.
        :param mixins: Subclasses of :code:`BaseException` to mix in.
        :return: The new exception type.
        """
        type_arg = mcs.error_type()
        if not isinstance(type_arg, type):
            if type_arg is Any:
                raise KWErrorErrors.NO_TYPE_ARG()
            raise KWErrorErrors.NOT_TYPE(obj=type_arg)
        if not issubclass(type_arg, KWError):
            raise KWErrorErrors.NOT_KW_ERROR(type=type_arg)
        typ = dataclass(super().__new__(mcs, '', (_KWError, type_arg) + tuple(mixins)))
        typ._compiled = compile(f'f{fmt!r}', '<string>', 'eval')
        return typ


class _GenEnumMeta(EnumMeta):
    # This metaclass is used to override __getitem__ for EnumMeta so that it uses __class_getitem__ instead of the
    # default behavior. This allows the existence of an Enum class which also inherits from Generic without errors
    # arising when type arguments are given to the Enum class (for instance, the default behavior for A[int] would be to
    # look for an enum member named "int" rather than to given a type alias for A parameterized with int.
    def __getitem__(cls, item: Any) -> Any:
        # noinspection PyUnresolvedReferences
        return cls.__class_getitem__(item)


class _GenEnum(Enum, metaclass=_GenEnumMeta):
    pass


class KWErrors2(_KWErrorsMeta[KWE], _GenEnum):
    def __getitem__(self, item: Any) -> Any:
        return getattr(self, item)

    def __str__(self) -> str:
        return eval(self._compiled, globals(), self)


class _KWErrors(Generic[KWE]):
    # This class contains the implementation details for KWErrors, which is defined publicly below in order to avoid
    # clashes between Generic.__class_getitem__ and Enum.__getitem__.

    #: Valid attributes. Implemented as an :code:`OrderedSet` in case a particular order of the attributes in string
    #: representations are desired.
    attrs: OrderedSet[str]

    #: The compiled f-string.
    compiled: CodeType

    @classmethod
    def error_type(cls) -> type[KWE]:
        """Get the exception type this context was parameterized with.

        :return: Exception type this context was parameterized with.
        """
        # Get the type arg this is parameterized with and raise an exception if is it not a subclass of KWError.
        import bobbeyreese.typing
        return typing.get_args(bobbeyreese.typing.infer_type_args(cls, _KWErrors))[0]

    def __init__(self, fmt: str, attrs: Iterable[str] = (), mixins: Iterable[type[BaseException]] = ()) -> None:
        """Initialize this error.

        :param fmt: Format string to use as an f-string.
        :param attrs: Attributes to recognize.
        :param mixins: Additional exception classes for this error to inherit from.
        """
        self.attrs = OrderedSet(attrs)
        self.compiled = compile(f'f{fmt!r}', '<string>', 'eval')

    def __call__(self, **kwargs: object) -> KWE:
        """Create a :class:`.KWError` using :code:`self` as its context.

        :param kwargs: Keyword argument to create :class:`.KWError` with.
        :return: The resulting :class:`.KWError`.
        :raise KWErrorError: If the type parameter passed to this context is either not a type or not a
            :class:`.KWError`.
        """
        type_arg = self.error_type()
        if isinstance(type_arg, type):
            if issubclass(type_arg, KWError):
                return type_arg(self, **kwargs)
            raise KWErrorErrors.NOT_KW_ERROR(type=type_arg)
        elif type_arg == Any:
            raise KWErrorErrors.NO_TYPE_ARG()
        raise KWErrorErrors.NOT_TYPE(obj=type_arg)

    def collect_errors(
        self,
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
        were raised, an exception of type :code:`KWE` is raised instead, with the given keyword arguments and an
        additional keyword argument corresponding to :code:`dest` has the dictionary as a value.

        :param args: Arguments to iterate over.
        :param fn: Function to call on each argument.
        :param typ: Type (or types) of exceptions to catch.
        :param dest: Name of attribute with which to set the error mapping. A value of :code:`None` will result in the
            mapping not being stored.
        :param key_fn: If supplied, use this function to determine the key in the resulting mapping for each argument
            instead of the argument itself.
        :param kwargs: Additional keyword arguments to construct the :code:`KWE` with.
        :raise KWE: If any exceptions of type :code:`typ` are raised during iteration.
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
            raise self(**kwargs)

    @contextmanager
    def wrap(self, ctx: KWErrors[KWE2], forward: bool | Iterable[str] = True, **kwargs: object) -> None:
        """Context manager which, upon a :code:`KWE2` with context :code:`ctx` being raised, instead raises a
        :code:`KWE` with the same attributes as the initially raised :code:`KWE2`. This of course requires that
        :code:`self.attrs == ctx.attrs`. Useful for keeping the behavior of another context but raising a different
            exception type.
        :param ctx: Context to wrap.
        :param forward: If :code:`True`, forward all keyword argument names and values from the caught exception to the
            raised exception. If :code:`False`, do not do any forwarding. If instead a collection is specified, all
            attributes from that collection will be forward and no others.
        :param kwargs: Additional keyword arguments to create the :code:`KWE` with.
        :raise KWE: If a :code:`KWE2` with the context :code:`ctx` is raised.
        """
        try:
            yield
        except ctx.error_type() as e:
            if e.ctx is not ctx:
                raise
            forwards = ctx.attrs if forward is True else () if not forward else forward
            for attr in forwards:
                kwargs[attr] = getattr(e, attr)
            raise self(**kwargs)

    @contextmanager
    def wrap_error(self, typ: Catchable, /, dest: str | None = 'error', **kwargs: object) -> None:
        """Context manager which, upon an exception of type :code:`typ` being raised, instead raises a :code:`KWE`
        constructed with the given keyword argument name :code:`dest` set to that error, and additional keyword
        arguments given by :code:`kwargs`.

        :param typ: Type (or types) of exception to catch.
        :param dest: Keyword argument with which to supply the wrapped error. A value of :code:`None` will result in the
            exception not being stored.
        :param kwargs: Additional keyword arguments to supply.
        :raise KWE: If an exception of type :code:`typ` is raised.
        """
        try:
            yield
        except typ as e:
            if dest is not None:
                kwargs[dest] = e
            raise self(**kwargs)


class KWErrors(_KWErrors[KWE], _GenEnum):
    """Class of objects which specify what format string to use and what attributes are valid for a :class:`.KWError`.
    This class subclasses :code:`Enum`: enum values for different kinds of errors should be specified using a tuple
    of :code:`(format string, recognized keywords)`.
    """


# Message to prefix all exception messages which occur in the course of initializing a KWError.
_INIT_FAILED_PREFIX: Final[str] = 'Failed to create KWError instance: '


# Message accompanying errors involving the generic argument to not being a subclass of KWError.
_TYPE_ERROR_HINT = (
    '(ErrorContext subclasses MUST supply a single concrete type parameter which is a subclass of KWError)'
)


class KWErrorError(KWError):
    """Errors which occur when using :class:`.KWError` itself. This class is *not* intended to be used by subclasses
    of :class:`.KWError`.
    """


class KWErrorErrors(KWErrors[KWErrorError]):
    """Context to use for :class:`.KWErrorError`."""
    ERR_MISMATCH = (
        _INIT_FAILED_PREFIX + 'type argument of {context.name} is "{actual.__name__}", not "{expected.__name__}".',
        ('context', 'actual', 'expected')
    )
    MISSING_ATTRS = (
        'The following attributes are expected by {context.name} but are missing: {", ".join(missing)}',
        ('context', 'missing')
    )
    MODIFICATION = 'KWErrors may not be modified.'
    NOT_KW_ERROR = (
        _INIT_FAILED_PREFIX + 'type argument "{type.__name__}" is not a KWError ' + _TYPE_ERROR_HINT, ('type',)
    )
    NOT_TYPE = _INIT_FAILED_PREFIX + 'type argument "{obj}" is not a type ' + _TYPE_ERROR_HINT, ('obj',)
    NO_TYPE_ARG = _INIT_FAILED_PREFIX + f'{KWErrors.__name__} subclasses must be given a type argument.'
    UNRECOGNIZED_ATTRS = (
        'The following attributes are unrecognized by {context.name}: {", ".join(unrecognized)}',
        ('context', 'unrecognized')
    )
