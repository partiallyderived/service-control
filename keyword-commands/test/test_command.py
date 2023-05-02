import copy
import unittest.mock as mock
from collections import OrderedDict
from unittest.mock import Mock

import enough
import pytest

from keywordcommands import (
    Arg, Command, CommandGroup, CommandState, Example, Parser, command
)
from keywordcommands.exceptions import (
    CommandErrors, CommandInitErrors, ExecutionError, ParseError
)

from conftest import cmd1_fn


def test_check_examples(cmd1: Command) -> None:
    # Test Command._check_examples, which should make sure the arguments of all
    # examples not marked as "unchecked" can be parsed without error.
    # The fixture examples, which should not generate errors, have already been
    # tested by this point, or else the command could not be constructed.
    args = [
        Arg('Argument 1', 'arg1'),
        Arg('Argument 2', 'arg2'),
        Arg('Argument 3', 'arg3')
    ]
    cmd1.examples = [Example(
        'Example 3',
        {'arg1': 'val1', 'arg2': 'val2', 'arg3': 'val3'},
        unchecked=False
    )]

    with enough.raises(CommandInitErrors.BadExample(
        args=args,
        error=CommandErrors.UnrecognizedArgs(
            unrecognized={'arg3'}, query=Command._void_state().query
        ),
        example=cmd1.examples[0]
    )):
        cmd1._check_examples(args)

    # If unchecked, should be permissible.
    cmd1.examples[0].unchecked = True
    cmd1._check_examples(args)


def test_check_signature(cmd1: Command) -> None:
    # Test Command._check_signature, which should raise an exception if the sole
    # positional argument of the supplied command is not 'state', or if there is
    # a mismatch between the names of the arguments passed to Command.__init__
    # and the keyword arguments for the function.

    # First, change which args are recognized by cmd and then expect an
    # exception.
    old_spec = copy.copy(cmd1.args)
    args = [Arg('Arg 1', 'arg1')]
    cmd1.args = {'arg1': Arg('Arg 1', 'arg1')}
    with enough.raises(CommandInitErrors.ExtraArgs(
        args=args, extra=['arg2'], fn=cmd1._fn)
    ):
        cmd1._check_signature(args)

    # Now add an additional arg and expect an exception.
    cmd1.args = {**old_spec, 'arg3': Arg('Arg 3', 'arg3')}
    with enough.raises(CommandInitErrors.MissingArgs(
        args=args, missing=['arg3'], fn=cmd1._fn)
    ):
        cmd1._check_signature(args)
    cmd1.args = old_spec

    # Now use a function with argument names containing uppercased characters
    # and expect an exception.
    # noinspection PyUnusedLocal, PyPep8Naming
    def cap_fn(state: CommandState, *, arg1: str, ArG2: str) -> None: pass

    cmd1._fn = cap_fn
    with enough.raises(CommandInitErrors.UppercasedArgs(
        upper=['ArG2'], fn=cap_fn)
    ):
        cmd1._check_signature(args)

    # Now try functions with variadic arguments and expect exceptions.
    # Positional var args.
    # noinspection PyUnusedLocal
    def var_args_fn(state: CommandState, *arg1: str, arg2: str) -> None: pass

    cmd1._fn = var_args_fn
    with enough.raises(CommandInitErrors.VariadicArg(
        arg='arg1', fn=var_args_fn)
    ):
        cmd1._check_signature(args)

    # Keyword var args.
    # noinspection PyUnusedLocal
    def kw_var_args_fn(state: CommandState, *, arg1: str, **arg2: str) -> None:
        pass

    cmd1._fn = kw_var_args_fn
    with enough.raises(CommandInitErrors.VariadicArg(
        arg='arg2', fn=kw_var_args_fn)
    ):
        cmd1._check_signature(args)

    # Both positional and keyword var args.
    # noinspection PyUnusedLocal
    def pos_and_kw_var_args(
        state: CommandState, *arg1: str, **arg2: str
    ) -> None: pass

    cmd1._fn = pos_and_kw_var_args
    # arg1 is the first variadic argument to appear.
    with enough.raises(CommandInitErrors.VariadicArg(
        arg='arg1', fn=pos_and_kw_var_args)
    ):
        cmd1._check_signature(args)

    # Now use a function with underscores corresponding to an arg with hyphens
    # and check that that works.
    # noinspection PyUnusedLocal
    def under_fn(
        state: CommandState, *, arg1: str, arg_2: str, __arg3__: str
    ) -> None: pass

    args = [
        Arg('Arg 1', 'arg1'), Arg('Arg 2', 'arg-2'), Arg('Arg 3', '--arg3--')
    ]
    Command('Command', under_fn, args=args)

    # Now make a function that has positional arguments differing from just
    # 'state'.

    # First: 1 positional argument which is not 'state'.
    # noinspection PyUnusedLocal
    def no_state(crate: CommandState, *, arg1: str, arg2: str) -> None: pass

    cmd1._fn = no_state
    with enough.raises(CommandInitErrors.NonStatePosArg(fn=no_state)):
        cmd1._check_signature(args)

    # Second: An extra positional argument.
    # noinspection PyUnusedLocal
    def extra_pos(
        state: CommandState, crate: CommandState, *, arg1: str, arg2: str
    ) -> None: pass

    cmd1._fn = extra_pos
    with enough.raises(CommandInitErrors.NonStatePosArg(fn=extra_pos)):
        cmd1._check_signature(args)

    # Third: No positional arguments.
    # noinspection PyUnusedLocal
    def no_pos(*, arg1: str, arg2: str) -> None: pass

    cmd1._fn = no_pos
    with enough.raises(CommandInitErrors.NonStatePosArg(fn=no_pos)):
        cmd1._check_signature(args)


def test_init(arg1: Arg, arg2: Arg, examples: list[Example]) -> None:
    # Test Command.__init__.
    # Mock the validation functions to ensure they are called.
    with mock.patch.multiple(
        Command,
        autospec=True,
        _check_examples=mock.DEFAULT,
        _check_signature=mock.DEFAULT
    ) as mocks:
        cmd = Command(
            'Command description',
            cmd1_fn,
            args=[arg1, arg2],
            examples=examples
        )
        mocks['_check_examples'].assert_called()
        mocks['_check_signature'].assert_called()
        assert cmd.args == OrderedDict([('arg1', arg1), ('arg2', arg2)])
        assert cmd._fn == cmd1_fn
        assert cmd._optional == {'arg2'}
        assert cmd.description == 'Command description'
        assert cmd.examples == examples


def test_arg_properties(arg1: Arg, arg2: Arg, cmd1: Command) -> None:
    # Test that Command.optional_args and Command.required_args correctly return
    # the optional and required arguments respectively.
    assert cmd1.required_args == [arg1]
    assert cmd1.optional_args == [arg2]


def test_arg(arg1: Arg, arg2: Arg, cmd1: Command) -> None:
    # Test that Command.arg gets an argument by a case-insensitive name.
    assert cmd1.arg('arg1') == arg1
    assert cmd1.arg('aRg1') == arg1
    assert cmd1.arg('arg2') == arg2
    assert cmd1.arg('arg3') is None


def test_parse(arg1: Arg, arg2: Arg, cmd1: Command) -> None:
    # First try with required args missing.
    with enough.raises(CommandErrors.MissingRequiredArgs(
        missing={'arg1'}, query=Command._void_state().query)
    ):
        cmd1.parse(None, {'arg2': 'value2'})

    # Now with extra args.
    with enough.raises(CommandErrors.UnrecognizedArgs(
        unrecognized={'arg3', 'arg4'}, query=cmd1._void_state().query
    )):
        cmd1.parse(None, {'arg1': 'value1', 'arg3': 'value3', 'arg4': 'value4'})

    # Try to succeed.
    assert cmd1.parse(None, {'arg1': 'value1'}) == {'arg1': 'value1'}
    assert cmd1.parse(
        None,
        {'arg1': 'value1', 'arg2': 'value2'}
    ) == {'arg1': 'value1', 'arg2': 'value2'}

    # Make a parser that can error and try again.
    parse_error = ParseError('msg')

    def int_parse_fn(x: str) -> int:
        try:
            return int(x)
        except ValueError:
            raise parse_error

    int_parser = Parser(int_parse_fn, 'An integer')
    for arg in cmd1.args.values():
        arg.parser = int_parser
    # Succeed first.
    assert cmd1.parse(
        None, {'arg1': '3', 'arg2': '5'}
    ) == {'arg1': 3, 'arg2': 5}

    # Now fail.
    with enough.raises(CommandErrors.ParseError(
        arg=arg1,
        value='string',
        error=parse_error,
        query=cmd1._void_state().query
    )):
        cmd1.parse(None, {'arg1': 'string'})

    # Try with hyphenated args.
    # noinspection PyShadowingNames, PyUnusedLocal
    def under_fn(
        state: CommandState, *, arg1: str, arg_2: str, __arg3__: str
    ) -> None: pass

    args = [
        Arg('Arg 1', 'arg1'), Arg('Arg 2', 'arg-2'), Arg('Arg 3', '--arg3--')
    ]
    cmd1 = Command('Command', under_fn, args=args)
    assert cmd1.parse(
        None, {
            'arg1': 'value1',
            'arg-2': 'value2', '--arg3--': 'value3'
        }
    ) == {'arg1': 'value1', 'arg_2': 'value2', '__arg3__': 'value3'}


def test_call(cmd1: Command) -> None:
    # Test Command.__call__, which should attempt to parse the given args and
    # then pass the parsed args to the supplied function.
    mock_fn = Mock()
    mock_root = Mock(spec=CommandGroup)
    state = CommandState('App', mock_root)
    state.query.text = ''
    cmd1._fn = mock_fn
    cmd1(state, {'arg1': 3, 'arg2': 5})
    mock_fn.assert_called_with(state, arg1=3, arg2=5)

    # Try when an ExecutionException is raised.
    error = ExecutionError('Execution error')
    mock_fn.side_effect = error
    with enough.raises(CommandErrors.ExecutionError(
        error=error, query=state.query
    )):
        cmd1(state, {'arg1': 3, 'arg2': 5})

    # Try when a different exception is raised, which will not be wrapped in
    # CommandFailedException.
    mock_fn.side_effect = ValueError
    with pytest.raises(ValueError):
        cmd1(state, {'arg1': 3, 'arg2': 5})


def test_commands_fn(cmd1: Command) -> None:
    # Test that Command.commands() includes only itself.
    assert cmd1.commands() == [([], cmd1)]


def test_paths(cmd1: Command) -> None:
    # Test that Command.paths() includes only itself.
    assert cmd1.paths() == [([], cmd1)]


def test_decorator(arg1: Arg, arg2: Arg, examples: list[Example]) -> None:
    # Test the command decorator.
    # noinspection PyShadowingNames, PyUnusedLocal
    @command('Command description', args=[arg1, arg2], examples=examples)
    def command_fn(
        state: CommandState, *, arg1: str, arg2: str = 'asdf'
    ) -> None: pass

    assert type(command_fn) == Command
    assert command_fn.description == 'Command description'
    assert command_fn.examples == examples
    assert command_fn.optional_args == [arg2]
    assert command_fn.required_args == [arg1]
