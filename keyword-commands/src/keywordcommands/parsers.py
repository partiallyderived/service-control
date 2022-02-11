"""This module contains parsers native to keyword-commands."""
from collections.abc import Callable

import enough as br
from enough import T

from keywordcommands.parser import ChainedParseError, ParseError, ParseFunction, Parser, parser
from keywordcommands.role import CommandRole
from keywordcommands.security import RolesSecurityManager, SecurityErrors
from keywordcommands.state import DefaultCommandState


def delimited(
    *,
    delim_name: str | None = None,
    delimiter: str = ',',
    elem_name: str = 'values'
) -> Callable[[ParseFunction[list[T]]], Parser[list[T]]]:
    """Decorator factory whose values turn callable functions into a delimited parser whose elements are parsed by that
    function.

    :param delim_name: Name of the delimiter to use in help messages. If unspecified, uses :code:`delimiter`, unless
        :code:`delimiter` is :code:`','` (the default), in which case :code:`'comma'` is used.
    :param delimiter: Delimiter to use.
    :param elem_name: Name of elements to use in help messages. Should be plural.
    :return: The resulting parser.
    """
    return lambda fn: delimited_parser(delim_name=delim_name, delimiter=delimiter, elem_name=elem_name, fn=fn)


def delimited_parser(
    *,
    delim_name: str | None = None,
    delimiter: str = ',',
    elem_name: str = 'values',
    fn: ParseFunction[list[T]] = br.identity
) -> Parser[list[T]]:
    """Creates a parser which parses a delimited sequence of strings into a :code:`list` of elements.

    :param delim_name: Name of the delimiter to use in help messages. If unspecified, uses :code:`delimiter`, unless
        :code:`delimiter` is :code:`','` (the default), in which case :code:`'comma'` is used.
    :param delimiter: Delimiter to use.
    :param elem_name: Name of elements to use in help messages. Should be plural.
    :param fn: The function to use to parse the elements. Uses identity function by default.
    :return: The resulting parser.
    :raise BadParseFunctionArgs: If :code:`fn` takes a number of arguments differing from 1 or 2.
    """
    if delim_name is None:
        if delimiter == ',':
            delim_name = 'comma'
        else:
            delim_name = delimiter
    fn = Parser.ensure_state_arg(fn)
    expected = f'{delim_name.capitalize()}-separated list of {elem_name}'
    return Parser(lambda arg, state: [fn(x, state) for x in arg.split(delimiter)], expected)


@parser('Any number')
def float_parser(arg: str) -> float:
    """Parses a floating-point number from a string.

    :param arg: String to parse.
    :return: The resulting floating point number
    :raise ParseError: If :code:`float(arg)` raises a :code:`ValueError`.
    """
    try:
        return float(arg)
    except ValueError:
        raise ParseError(f'{arg} is not a valid number.')


@parser('An integer')
def int_parser(arg: str) -> int:
    """Parses an integer from a string.

    :param arg: String to parse.
    :return: The resulting integer.
    :raise ParseError: If :code:`int(arg)` raises a :code:`ValueError`.
    """
    try:
        return int(arg)
    except ValueError:
        raise ParseError(f'{arg} is not a valid integer.')


@parser('A role')
def role_parser(name: str, state: DefaultCommandState) -> CommandRole:
    """Parse a :class:`.CommandRole` from the given name.

    :param name: Name of the role to parse.
    :param state: Current command state.
    :return: The parsed role.
    :raise ChainedParseError: If no role with the given name could be found. The underlying error will be a
        :class:`.SecurityError`.
    :raise TypeError: If :code:`state.security_manager` is not a :class:`.RolesSecurityManager`.
    """
    manager = state.security_manager
    if not isinstance(manager, RolesSecurityManager):
        raise TypeError(f'Security manager {manager} is not an instance of {RolesSecurityManager.__name__}.')
    try:
        return manager.role(name)
    except SecurityErrors.NoSuchRole as e:
        raise ChainedParseError(e)


#: Parse a comma-separated list of role names into a list of :class:`.CommandRole` instances.
roles_parser = delimited_parser(elem_name='roles', fn=role_parser)
