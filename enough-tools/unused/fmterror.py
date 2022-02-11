from __future__ import annotations

import sys
import traceback
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from types import CodeType
from typing import ClassVar, Generic

from bobbeyreese.types import EV


@dataclass
class FmtError(Exception, ABC):
    """Base class of exceptions which generate their exception message via a format string class var called
    :code:`_fmt`. The message is constructed as though :code:`_fmt` is an f-string with local variables coming from
    :code:`instance._vars()` (:code:`instance.__dict__` by default).
    """

    # Compiled format string.
    _compiled: ClassVar[CodeType | None] = None

    #: Format string to use to format the exception with. Must be implemented by subclasses.
    @property
    @abstractmethod
    def _fmt(self) -> str:
        ...

    @classmethod
    def _compiled_fmt(cls) -> CodeType:
        # Lazily compile _fmt.
        if not cls._compiled:
            cls._compiled = compile(f'f{repr(cls._fmt)}', '<string>', 'eval')
        return cls._compiled

    def __str__(self) -> str:
        """Gives the string representation of this exception given by :code:`self.msg`.

        :return: :code:`self.msg`.
        """
        return eval(self._compiled_fmt(), globals(), self._vars())

    def _vars(self) -> dict[str, object]:
        """Gives the dictionary from variable names to values that will be used to evaluate the :code:`_fmt` f-string.
        By default, returns :code:`self.__dict__`. It is highly recommended to merge the resulting dictionary with the
        dictionary of the super class like so :code:`return {**super()._vars(), ...}`.

        :return: Mapping from variable names to values to use to evaluate the :code:`_fmt` f-string.
        """
        return {**self.__dict__, 'args': self.args}


@dataclass
class MissingCauseError(FmtError, Generic[EV]):
    """Raised when :meth:`bobbeyreese.fmterror.ChainedFmtError.__init__` does not receive the :code:`error` argument
    and the error cannot be inferred from :code:`sys.exc_info`.
    """
    _fmt: ClassVar[str] = '__init__ received no error argument and no error could be inferred from sys.exc_info.'


@dataclass
class ChainedFmtError(FmtError, Generic[EV]):
    """Base class of :class:`FmtErrors <.FmtError>` which have an error attribute."""
    #: Error for which this error is chained.
    error: EV = None

    def __post_init__(self) -> None:
        """See if :code:`error` was  specified in :code:`bobbeyreese.fmterror.ChainedFmtError.__init__`. If it was not,
        try to set it from :code:`sys.exc_info`.

        :raise NotImplementedError: If :code:`_fmt` is undefined.
        :raise MissingCauseError: If :code:`error` was not specified and no error could be inferred from
        :code:`sys.exc_info`.
        """
        # Try to set error from sys.exc_info() if it is missing.
        if self.error is None:
            self.error = sys.exc_info()[1]
            if self.error is None:
                raise MissingCauseError()

    def _vars(self) -> dict[str, object]:
        # Use _error_msg to generate the error message.
        return {**super()._vars(), 'error': ''.join(traceback.format_exception(self.error))}


@dataclass(kw_only=True)
class ImportFmtError(FmtError, ImportError):
    """Flavor of :class:`.FmtError` which subclasses :code:`ImportError`. This super class allows usage of the "name"
    and "path" parameters for use in expanding the f-string :code:`_fmt`.
    """

    @property
    def msg(self) -> str:
        # Overwrite this property to return self.__str__.
        return str(self)

    def _vars(self) -> dict[str, object]:
        # Put name and path explicitly here since they are properties of ImportError and won't be found in
        # self.__dict__.
        return {**super()._vars(), 'name': self.name, 'path': self.path}


@dataclass
class MultiFmtError(FmtError, Generic[EV]):
    """Base class of :class:`FmtErrors <.FmtError>` which have multiple errors."""

    #: Exceptions associated with this error.
    errors: Iterable[EV]

    def _vars(self) -> dict[str, object]:
        # For each error, generate their error message using _error_msg. Separate each error message with two new lines.
        return {**super()._vars(), 'errors': '\n\n'.join(''.join(traceback.format_exception(e)) for e in self.errors)}
