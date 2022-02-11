from __future__ import annotations

import inspect
import traceback
import typing
from typing import Callable, ClassVar, Generic

import enough as br
from enough import EnumErrors, V

import keywordcommands.util as util
from keywordcommands._exceptions import KeywordCommandsError, WrappedException

if typing.TYPE_CHECKING:
    from keywordcommands import CommandState

# Type of functions for which a parser may be created.
ParseFunction = Callable[[str], V] | Callable[[str, 'CommandState | None'], V]


class ParseError(KeywordCommandsError):
    """Exception to raise to indicate that a foreseen parsing error occurred in a parse function."""


class ChainedParseError(ParseError, WrappedException):
    """Exception to raise when a :class:`.ParsingException` results from another exception."""


class ParserInitErrors(EnumErrors[KeywordCommandsError]):
    """Exception types raised in keywordcommands.parser."""
    BadKWArgs = 'The given function has keyword-only arguments without defaults.', 'fn'
    BadNumArgs = 'The given functions takes {num_args} positional arguments when either 1 or 2 are expected.', 'fn'

    @property
    def num_args(cls) -> int:
        return util.num_required_pos_args(cls.fn)


class Parser(Generic[V]):
    """Represents an argument parser."""
    #: The default parser to use which just returns the original string.
    DEFAULT: ClassVar[Parser[str]] = None

    #: String containing a description of how arguments parsed by this parser should be formatted.
    expected_format: str

    #: Function which does the parsing.
    fn: Callable[[str, CommandState | None], V]

    @staticmethod
    def ensure_state_arg(fn: ParseFunction[V]) -> Callable[[str, CommandState], V]:
        """If :code:`fn` takes a single argument, convert it to a function containing two arguments. The second argument
        is the unused state. If :code:`fn` already takes two arguments, it is returned instead.
        
        :param fn: Function to convert.
        :return: Parse function taking two arguments.
        :raise ParserInitError: If :code:`fn` takes a number of positional arguments differing from 1 or 2, or if it
            has keyword-only arguments without defaults.
        """
        try:
            spec = inspect.getfullargspec(fn)
        except TypeError:
            if 'no signature found for builtin type' in traceback.format_exc():
                # Assume the built-in type takes a single argument as a means of conversion to it.
                return lambda arg, state: fn(arg)
            raise
        # Note that spec.kwonlydefaults is None if no arguments are keyword-only.
        if len(spec.kwonlyargs) != len(spec.kwonlydefaults or ()):
            raise ParserInitErrors.BadKWArgs(fn=fn)

        # Subtract self parameter if this is a bound method.
        match util.num_required_pos_args(fn):
            case 1:
                return lambda arg, state: fn(arg)
            case 2:
                return fn
            case _:
                raise ParserInitErrors.BadNumArgs(fn=fn)

    def __init__(self, fn: ParseFunction[V], expected_format: str) -> None:
        """Creates a parser using the given parse function.

        :param fn: Parse function to use. The first argument it takes should be the string argument to parse, while
            the second argument is the current state. Optionally, the function may take only one string argument and
            omit the state argument.
        :param expected_format: String which serves as a user message for how arguments should be formatted.
        :raise ParserInitError: If :code:`fn` takes a number of positional arguments differing from 1 or 2, or if it
            has keyword-only arguments without defaults.
        """
        self.fn = self.ensure_state_arg(fn)
        self.expected_format = expected_format

    def __call__(self, arg: str, state: CommandState | None = None) -> V:
        """Parses the given arguments.

        :param arg: Argument to parse.
        :param state: Current command state.
        :return: The parsed result.
        """
        return self.fn(arg.strip(), state)


Parser.DEFAULT = Parser(br.identity, 'Anything')


def parser(expected_format: str) -> Callable[[ParseFunction[V]], Parser[V]]:
    """Decorator factory whose values can be used to convert a function into a :class:`.Parser`. That function should
    take either a single string argument or a string argument and a :class:`.CommandState` argument.

    :param expected_format: String containing a description of how arguments parsed by this parser should be formatted.
    :return: Decorator which converts functions into parsers.
    """
    return lambda fn: Parser(fn, expected_format)
