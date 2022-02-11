import pytest

import keywordcommands.parsers as parsers
from keywordcommands import CommandRole, Parser
from keywordcommands.exceptions import ParseError

from conftest import StrUserState


def test_delimited_parser() -> None:
    # Test parsers.delimited_parser.
    # Default should be comma-separated string parser.
    parser = parsers.delimited_parser()
    assert parser.expected_format == 'Comma-separated list of values'
    assert parser('1,2,3,4') == ['1', '2', '3', '4']

    # Try same thing, but with int as function.
    parser = parsers.delimited_parser(elem_name='integers', fn=int)
    assert parser.expected_format == 'Comma-separated list of integers'
    assert parser('1,2,3,4') == [1, 2, 3, 4]

    # Check behavior of delim_name and delimiter.
    parser = parsers.delimited_parser(delim_name='semi-colon', delimiter=';')
    assert parser.expected_format == 'Semi-colon-separated list of values'
    assert parser('1,2,3,4') == ['1,2,3,4']
    assert parser('1;2;3;4') == ['1', '2', '3', '4']

    # Check that the delimiter is used as its own name by default.
    parser = parsers.delimited_parser(delimiter=':')
    assert parser.expected_format == ':-separated list of values'


def test_delimited_decorator_factory() -> None:
    # Test parsers.delimited, whose return values are decorators which turn functions into delimited parsers which call
    # that function to parse each element.

    # Default should be comma-separated parser.
    @parsers.delimited()
    def int_csv_parser(arg: str) -> int:
        return int(arg)

    assert type(int_csv_parser) == Parser
    assert int_csv_parser.expected_format == 'Comma-separated list of values'
    assert int_csv_parser('1,2,3,4') == [1, 2, 3, 4]

    # Now with parameters.
    @parsers.delimited(delim_name='semi-colon', delimiter=';', elem_name='integers')
    def int_semi_colon_parser(arg: str) -> int:
        return int(arg)

    assert int_semi_colon_parser.expected_format == 'Semi-colon-separated list of integers'
    assert int_semi_colon_parser('1;2;3;4') == [1, 2, 3, 4]

    # Check that the delimiter uses itself as its name by default.
    @parsers.delimited(delimiter=':')
    def parser(arg: str) -> str:
        return arg

    assert parser.expected_format == ':-separated list of values'
    assert parser('1,2,3,4') == ['1,2,3,4']
    assert parser('1:2:3:4') == ['1', '2', '3', '4']


def test_float_parser() -> None:
    # Test parsers.float_parser.
    assert parsers.float_parser.expected_format == 'Any number'
    assert parsers.float_parser('3.14') == 3.14
    assert parsers.float_parser('2.72') == 2.72

    # Expect ParseError rather than ValueError.
    with pytest.raises(ParseError):
        parsers.float_parser('Word')


def test_int_parser() -> None:
    # Test parsers.int_parser.
    assert parsers.int_parser.expected_format == 'An integer'
    assert parsers.int_parser('3') == 3
    assert parsers.int_parser('1000') == 1000

    # Expect ParseError rather than ValueError.
    with pytest.raises(ParseError):
        parsers.int_parser('Word')


def test_role_parser(user_state: StrUserState, role_empty: CommandRole) -> None:
    # Test parsers.role_parser, which should parse a CommandRole from a str.
    assert parsers.role_parser.expected_format == 'A role'
    assert parsers.role_parser('empty', user_state) == role_empty
    assert parsers.role_parser('eMpTy', user_state) == role_empty


def test_roles_parser(
    user_state: StrUserState, role_empty: CommandRole, role1: CommandRole, role2: CommandRole
) -> None:
    # Test parsers.roles_parser, which should parse multiple CommandRoles from a comma-separated string.
    assert parsers.roles_parser.expected_format == 'Comma-separated list of roles'
    assert parsers.roles_parser('empty,RoLe1,ROLE2', user_state) == [role_empty, role1, role2]
