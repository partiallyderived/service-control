import copy
import unittest.mock as mock
from collections import OrderedDict

import enough
import pytest

import keywordcommands.format
from keywordcommands import (
    Arg,
    Command,
    CommandGroup,
    DefaultQueryFormatFns,
    DefaultQueryFormatter,
    Example,
    Parser,
    QueryInfo,
    QueryResult
)
from keywordcommands.exceptions import CommandErrors, FormatErrors


def test_compose_formats() -> None:
    # Test keywordcommands.format.compose_fmts, which should take a mapping from
    # format fields to format strings, where each format field in the string is
    # replaced by the corresponding expanded format string.
    assert keywordcommands.format.compose_fmts({
        'field1': 'fmt1',
        'field2': 'fmt2 {field1}',
        'field3': '{field2}{field1}'
    }
    ) == {'field1': 'fmt1', 'field2': 'fmt2 fmt1', 'field3': 'fmt2 fmt1fmt1'}

    # ignore kwarg allows some format fields to be left untouched.
    assert keywordcommands.format.compose_fmts(
        {
            'field1': 'val is {val1}',
            'field2': '{field1} {val2}', 'field3':
            '{field2} {val3}'
        },
        ignore={'val1', 'val2', 'val3'}
    ) == {
        'field1': 'val is {val1}',
        'field2': 'val is {val1} {val2}',
        'field3': 'val is {val1} {val2} {val3}'
    }

    # Try when a field is both ignored and included.

    with enough.raises(FormatErrors.ComposeFieldNameCollision(
        colliding={'val1', 'val2'}
    )):
        keywordcommands.format.compose_fmts(
            {
                'field1': '{val1}',
                'field2': '{val2}',
                'field3': '{val3}',
                'val1': 'asdf',
                'val2': 'fdsa'
            },
            ignore={'val1', 'val2', 'val3'}
        )

    # Try when there are missing unignored fields.
    with enough.raises(
        FormatErrors.ComposeMissingFields(missing={'val2', 'val3'})
    ):
        keywordcommands.format.compose_fmts(
            {'field1': '{val1}', 'field2': '{val2}', 'field3': '{val3}'},
            ignore={'val1'}
        )

    # Test when there is a circular dependency.
    # noinspection PyTypeChecker
    with pytest.raises(FormatErrors.CircularDependency) as exc_info:
        keywordcommands.format.compose_fmts({
            'field1': '{field2}', 'field2': '{field3}', 'field3': '{field1}'
        })
    # Three possibilities for the cycle path.
    assert exc_info.value.path in [
        ['field1', 'field2', 'field3', 'field1'],
        ['field2', 'field3', 'field1', 'field2'],
        ['field3', 'field1', 'field2', 'field3']
    ]


def test_default_query_format_fns() -> None:
    # Test the default implementation of the QueryFormatFns ABC.
    format_fns = DefaultQueryFormatFns()
    fns = format_fns.fmt_fns()

    parser1 = Parser(lambda x: x, 'Anything')
    parser2 = Parser(lambda x: int(x), 'An integer')
    arg1 = Arg('Argument 1.', 'arg1', parser1)
    arg2 = Arg('Argument 2.', 'arg2', parser2)
    arg3 = Arg('Argument 3.', 'arg3', parser1)
    arg4 = Arg('Argument 4.', 'arg4', parser2)
    example1 = Example(
        'does something.', OrderedDict([('arg1', 'val1'), ('arg2', '5')])
    )
    example2 = Example(
        'does something else.', OrderedDict([('arg1', 'VAL1'), ('arg2', '6')])
    )
    # noinspection PyShadowingNames
    cmd1 = Command(
        'Command 1.',
        lambda state, *, arg1, arg2, arg3='asdf', arg4=5: None,
        args=[arg1, arg2, arg3, arg4],
        examples=[example1, example2]
    )
    cmd2 = Command('Command 2.', lambda state: None)
    cmd3 = Command('Command 3.', lambda state: None)
    group = CommandGroup('Group.', edge1=cmd1, edge2=cmd2)
    root = CommandGroup('Root.', edge3=group, edge4=cmd3)
    query = QueryInfo('App', root)
    query.text = 'edge3 edge1'
    query.path = ['edge3', 'edge1']

    # Test formatting that does not depend or specifically relate to how node or
    # error is set.
    assert fns['app'](query) == 'App'
    assert fns['path'](query) == 'edge3 edge1'
    assert format_fns.fmt_coll(
        ['first', 'second', 'third']
    ) == 'first, second, third'

    # Test formatting command information.
    query.node = cmd1

    # Description should be uncapitalized.
    assert fns['cmd_desc'](query) == 'command 1.'
    assert format_fns.fmt_cmd_short(
        cmd1, ['edge3', 'edge1']
    ) == 'edge3 edge1: Command 1.'

    # Test formatting the command's examples.
    expected_example_lines = [
        'Example: "edge3 edge1 arg1=val1 arg2=5" does something.',
        'Example: "edge3 edge1 arg1=VAL1 arg2=6" does something else.'
    ]
    assert format_fns.fmt_example(
        example1, query.path
    ) == expected_example_lines[0]
    assert format_fns.fmt_examples(
        cmd1.examples, query.path
    ) == '\n'.join(expected_example_lines)
    assert fns['examples'](query) == '\n'.join(expected_example_lines)

    # Test formatting the command's arguments.
    expected_required_lines = [
        'arg1: Argument 1. Expected value: Anything',
        'arg2: Argument 2. Expected value: An integer'
    ]
    expected_indented_required = [
        f'    {line}' for line in expected_required_lines
    ]
    expected_optional_lines = [
        'arg3: Argument 3. Expected value: Anything',
        'arg4: Argument 4. Expected value: An integer'
    ]
    expected_indented_optional = [
        f'    {line}' for line in expected_optional_lines
    ]
    assert format_fns.fmt_arg(arg1) == expected_required_lines[0]
    assert format_fns.fmt_args(
        [arg1, arg2], indent=0
    ) == '\n'.join(expected_required_lines)
    assert format_fns.fmt_args(
        [arg1, arg2], indent=4
    ) == '\n'.join(expected_indented_required)
    assert fns['required_args'](query) == '\n'.join(expected_required_lines)
    assert fns['optional_args'](query) == '\n'.join(expected_optional_lines)
    assert fns['indented_required_args'](
        query
    ) == '\n'.join(expected_indented_required)
    assert fns['indented_optional_args'](
        query
    ) == '\n'.join(expected_indented_optional)

    assert fns['indented_optional_args'](query) == (
        '    arg3: Argument 3. Expected value: Anything\n'
        '    arg4: Argument 4. Expected value: An integer'
    )

    # Test formatting group information.
    query.node = group
    assert fns['group_desc'](query) == 'group.'  # Should be uncapitalized.
    assert fns['root_desc'](query) == root.description
    expected_cmd_lines = [
        'edge3 edge1: Command 1.',
        'edge3 edge2: Command 2.'
    ]
    expected_root_lines = expected_cmd_lines + ['edge4: Command 3.']
    query.path = ['edge3']
    assert format_fns.fmt_cmds(
        group, ['edge3']
    ) == '\n'.join(expected_cmd_lines)
    assert fns['cmds'](query) == '\n'.join(expected_cmd_lines)
    assert fns['root_cmds'](query) == '\n'.join(expected_root_lines)

    # Test error formatting.
    query.error = CommandErrors.DuplicateArgs(
        duplicated=['1', '2', '3'], query=query
    )
    assert fns['duplicated_args'](query) == '1, 2, 3'
    assert fns['error'](query) == str(query.error)

    query.error = CommandErrors.ParseError(
        arg=arg1, value='val1', error=ValueError(), query=query
    )
    assert fns['err_actual'](query) == 'val1'
    assert fns['err_arg'](query) == 'arg1'
    assert fns['err_expected'](query) == 'Anything'

    query.error = CommandErrors.MissingRequiredArgs(
        missing=['arg1', 'arg2'], query=query
    )
    assert fns['missing_args'](query) == 'arg1, arg2'

    query.error = CommandErrors.UnrecognizedArgs(
        unrecognized=['arg5', 'arg6'], query=query
    )
    assert fns['unrecognized_args'](query) == 'arg5, arg6'

    with mock.patch('traceback.format_exception') as mock_fmt_exc:
        mock_fmt_exc.return_value = 'An unexpected failure occurred'
        error = ValueError()
        query.error = CommandErrors.UnexpectedError(error=error, query=query)
        assert format_fns.fmt_unexpected(
            query.error
        ) == 'An unexpected failure occurred'
        assert fns['unexpected'](query) == mock_fmt_exc.return_value
        mock_fmt_exc.assert_called_with(error)


def test_default_query_formatter() -> None:
    # Test the default implementation of the QueryFormatter ABC.

    # Test __init__ exceptions.
    field_to_fmt = {'field1': 'value1', 'field2': '{field1} value2 {path}'}
    format_fns = {'path': lambda q: ':'.join(q.path)}
    result_to_field = {
        QueryResult.SUCCESS: None,
        QueryResult.GENERAL_HELP: None,
        QueryResult.GROUP_HELP: 'field1',
        QueryResult.CMD_HELP: None,
        QueryResult.HELP_NOT_FOUND: None,
        CommandErrors.DuplicateArgs: None,
        CommandErrors.MissingPath: None,
        CommandErrors.NoSuchPath: None,
        CommandErrors.NotCommand: None,
        CommandErrors.MissingRequiredArgs: None,
        CommandErrors.UnrecognizedArgs: None,
        CommandErrors.ParseError: None,
        CommandErrors.ExecutionError: 'field2',
        CommandErrors.UnexpectedError: None
    }

    # Missing a QueryResult format string should result in an exception.
    result_to_field_with_missing = copy.copy(result_to_field)
    del result_to_field_with_missing[QueryResult.GENERAL_HELP]
    del result_to_field_with_missing[CommandErrors.UnexpectedError]
    with enough.raises(
        FormatErrors.MissingResultFields(
            missing={QueryResult.GENERAL_HELP, CommandErrors.UnexpectedError}
        )
    ):
        DefaultQueryFormatter(
            field_to_fmt=field_to_fmt,
            fmt_fns=format_fns,
            result_to_field=result_to_field_with_missing
        )

    # Missing a format field that appears in result_to_field should result in an
    # exception.
    result_to_field_with_unrecognized = copy.copy(result_to_field)
    result_to_field_with_unrecognized[QueryResult.SUCCESS] = 'field3'
    result_to_field_with_unrecognized[CommandErrors.NotCommand] = 'field4'
    with enough.raises(FormatErrors.FormatterMissingFields1(
        missing={'field3', 'field4'}
    )):
        DefaultQueryFormatter(
            field_to_fmt=field_to_fmt,
            fmt_fns=format_fns,
            result_to_field=result_to_field_with_unrecognized
        )

    # Now try to succeed with default.
    DefaultQueryFormatter()

    # Now try with our test objects.
    formatter = DefaultQueryFormatter(
        field_to_fmt=field_to_fmt,
        fmt_fns=format_fns,
        result_to_field=result_to_field
    )
    assert formatter.field_to_format == {
        'field1': 'value1', 'field2': 'value1 value2 {path}'
    }
    query = QueryInfo('app', CommandGroup('root'))
    query.path = ['edge1', 'edge2']

    query.result = QueryResult.GENERAL_HELP
    assert formatter.user_msg(query) is None

    query.result = QueryResult.GROUP_HELP
    assert formatter.user_msg(query) == 'value1'

    query.result = CommandErrors.ExecutionError
    assert formatter.user_msg(query) == 'value1 value2 edge1:edge2'

    query.result = None
    with enough.raises(FormatErrors.NoResult(query=query)):
        formatter.user_msg(query)
