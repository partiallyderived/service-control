import unittest.mock as mock
from unittest.mock import Mock

import enough

from keywordcommands import (
    Arg,
    Command,
    CommandGroup,
    CommandHandler,
    CommandState,
    DefaultCommandHandler,
    DefaultCommandState,
    Parser,
    QueryFormatter,
    QueryResult,
    SecurityManager
)
from keywordcommands.exceptions import (
    CommandErrors, ExecutionError, ParseError, SecurityError
)


def test_parse() -> None:
    # Test that CommandHandler.parse correctly parses the path and keyword
    # arguments for the given string.
    assert CommandHandler.parse('') == ([], {}, set())
    assert CommandHandler.parse(
        'edge1 edge2 edge3'
    ) == (['edge1', 'edge2', 'edge3'], {}, set())
    assert CommandHandler.parse(
        'help edge1 edge2 edge3'
    ) == (['help', 'edge1', 'edge2', 'edge3'], {}, set())
    assert CommandHandler.parse(
        'arg1=val1 arg2=val2 arg3=val3'
    ) == ([], {'arg1': 'val1', 'arg2': 'val2', 'arg3': 'val3'}, set())
    assert CommandHandler.parse(
        'edge1 edge2 edge3 arg1=val1 arg2=val2 arg3=val3'
    ) == (
        ['edge1', 'edge2', 'edge3'],
        {'arg1': 'val1', 'arg2': 'val2', 'arg3': 'val3'},
        set()
    )

    # Try spacing things out, should get same result.
    assert CommandHandler.parse(
        'edge1  edge2      edge3      arg1=val1  arg2=val2       arg3=val3'
    ) == (
        ['edge1', 'edge2', 'edge3'],
        {'arg1': 'val1', 'arg2': 'val2', 'arg3': 'val3'},
        set()
    )

    # Edges and argument keys are case insensitive.
    assert CommandHandler.parse(
        'edge1 EDGE2 edge3 arg1=val1 ARG2=VAL2 arg3=val3'
    ) == (
        ['edge1', 'edge2', 'edge3'],
        {'arg1': 'val1', 'arg2': 'VAL2', 'arg3': 'val3'},
        set()
    )

    # Duplicates are given in third return value.
    assert CommandHandler.parse(
        'edge1 edge2 edge3 arg1=val1 ARG1=VAL1 arg2=val2 arg2=VAL2 arg3=val3'
    ) == (
        ['edge1', 'edge2', 'edge3'],
        {'arg1': 'VAL1', 'arg2': 'VAL2', 'arg3': 'val3'},
        {'arg1', 'arg2'}
    )

    _, kwargs, _ = CommandHandler.parse(
        r'edge1 edge2 edge3 arg1=hi\=everybody arg2=val2'
    )
    print(kwargs['arg1'].count('\\'))

    # Try escaping equals sign.
    assert CommandHandler.parse(
        r'edge1 edge2 edge3 arg1=hi\=everybody arg2=val2'
    ) == (
        ['edge1', 'edge2', 'edge3'],
        {'arg1': r'hi=everybody', 'arg2': 'val2'},
        set()
    )

    # More complicated escape.
    assert CommandHandler.parse(
        r'edge1 edge2 edge3 arg1=hello\\\\\=Dr. Nick arg2=val2'
    ) == (
        ['edge1', 'edge2', 'edge3'],
        {'arg1': r'hello\\\\=Dr. Nick', 'arg2': 'val2'},
        set()
    )

    # Edge case: empty value for an argument.
    assert CommandHandler.parse('edge1 edge2 edge3 arg1=arg2=val2') == (
        ['edge1', 'edge2', 'edge3'], {'arg1': '', 'arg2': 'val2'}, set()
    )

    # Same thing but with trailing whitespace.
    assert CommandHandler.parse('edge1 edge2 edge3 arg1=  arg2=val2') == (
        ['edge1', 'edge2', 'edge3'], {'arg1': '', 'arg2': 'val2'}, set()
    )


def test_handle() -> None:
    # Test CommandHandler's instance methods.

    mock_methods = Mock(spec=CommandHandler)
    all_mocks = [
        mock_methods.handle_cmd_help,
        mock_methods.handle_error,
        mock_methods.handle_general_help,
        mock_methods.handle_group_help,
        mock_methods.handle_help_not_found,
        mock_methods.handle_success,
        mock_methods.pre_execute
    ]

    def assert_only_called(*called: Mock) -> None:
        # Assert that the given arg was called and that all others were not.
        [c.assert_called_with(state) for c in called]
        [c.reset_mock() for c in called]
        [m.assert_not_called() for m in all_mocks]
        state.reset()

    class MockCommandHandler(CommandHandler):
        def handle_cmd_help(self, s: CommandState) -> None:
            mock_methods.handle_cmd_help(s)

        def handle_error(self, s: CommandState) -> None:
            mock_methods.handle_error(s)

        def handle_general_help(self, s: CommandState) -> None:
            mock_methods.handle_general_help(s)

        def handle_group_help(self, s: CommandState) -> None:
            mock_methods.handle_group_help(s)

        def handle_help_not_found(self, s: CommandState) -> None:
            mock_methods.handle_help_not_found(s)

        def handle_success(self, s: CommandState) -> None:
            mock_methods.handle_success(s)

        def pre_execute(self, s: CommandState) -> None:
            mock_methods.pre_execute(s)

    # Errors we will use for exception equality testing.
    exe_error = ExecutionError('Execution error')
    parse_error = ParseError('Parse error')
    unexpected_error = ValueError()

    # Parser for the command arguments.
    def parse_fn(arg: str) -> str:
        if arg == 'parse-fail':
            # Useful for testing exceptional cases.
            raise parse_error
        return arg

    parser = Parser(parse_fn, 'Anything')

    # Arguments for the commands.
    arg1 = Arg('Argument 1', 'arg1', parser)
    arg2 = Arg('Argument 2', 'arg2', parser)
    arg3 = Arg('Argument 3', 'arg3', parser)
    arg4 = Arg('Argument 4', 'arg4', parser)

    # Functions for commands.
    # noinspection PyUnusedLocal, PyShadowingNames
    def cmd_fn1(state, *, arg1: str, arg2: str = 'asdf') -> None:
        if arg1 == 'cmd-fail':
            raise exe_error
        if arg1 == 'unexpected':
            raise unexpected_error

    # noinspection PyUnusedLocal, PyShadowingNames
    def cmd_fn2(state, *, arg3: str, arg4: str = 'fdsa') -> None: pass

    # Useful to have a concrete group and some commands to test with.
    cmd1 = Command('Command 1', cmd_fn1, args=[arg1, arg2])
    cmd2 = Command('Command 2', cmd_fn2, args=[arg3, arg4])
    group = CommandGroup('Group', edge1=cmd1)
    root = CommandGroup('Root', edge2=cmd2, edge3=group)
    state = CommandState(name='App', root=root)
    handler = MockCommandHandler()

    # Case 1: General help from empty command string.
    handler.handle(state, '')
    assert state.query.result == QueryResult.GENERAL_HELP
    assert state.query.path == []
    assert state.query.text == ''

    # Bundle in a test for reset() before making mock assertions.
    state.reset()
    assert state.query.path is None
    assert state.query.result is None
    assert state.query.text is None
    assert state.query.name == 'App'
    assert state.query.root == root

    # Make mock assertions and reset mocks.
    assert_only_called(mock_methods.handle_general_help)

    # Case 2: General help from "help" as entire path input.
    handler.handle(state, 'help')
    assert state.query.result is QueryResult.GENERAL_HELP
    assert state.query.path == []
    assert state.query.text == 'help'
    assert_only_called(mock_methods.handle_general_help)

    # Case 3: Help for a command.
    handler.handle(state, 'help edge3 edge1')
    assert state.query.result is QueryResult.CMD_HELP
    assert state.query.path == ['edge3', 'edge1']
    assert state.query.node == cmd1
    assert state.query.text == 'help edge3 edge1'
    assert_only_called(mock_methods.handle_cmd_help)

    # Case 4: Help for a command group.
    handler.handle(state, 'help edge3')
    assert state.query.result is QueryResult.GROUP_HELP
    assert state.query.path == ['edge3']
    assert state.query.node == group
    assert_only_called(mock_methods.handle_group_help)

    # Case 5: Help for command that can't be found.
    handler.handle(state, 'help edge3 edge2')
    assert state.query.result is QueryResult.HELP_NOT_FOUND
    assert state.query.path == ['edge3', 'edge2']
    assert state.query.node is None
    assert_only_called(mock_methods.handle_help_not_found)

    # Case 6: Malformed path.
    handler.handle(state, 'edge3 edge!')
    assert state.query.error == CommandErrors.NoSuchPath(query=state.query)
    assert state.query.result is CommandErrors.NoSuchPath
    assert state.query.path == ['edge3', 'edge!']
    assert state.query.node is None
    assert_only_called(mock_methods.handle_error)

    # Case 7: No such path.
    handler.handle(state, 'edge3 edge2')
    assert state.query.error == CommandErrors.NoSuchPath(query=state.query)
    assert state.query.result is CommandErrors.NoSuchPath
    assert state.query.path == ['edge3', 'edge2']
    assert state.query.node is None
    assert_only_called(mock_methods.handle_error)

    # Case 8: Not a command.
    handler.handle(state, 'edge3')
    assert state.query.error == CommandErrors.NotCommand(query=state.query)
    assert state.query.result is CommandErrors.NotCommand
    assert state.query.path == ['edge3']
    assert state.query.node == group
    assert_only_called(mock_methods.handle_error)

    # Case 9: Duplicate args.
    handler.handle(state, 'edge3 edge1 arg1=val1 ARG1=VAL1 arg2=val2')
    assert state.query.error == CommandErrors.DuplicateArgs(
        duplicated={'arg1'}, query=state.query
    )
    assert state.query.result == CommandErrors.DuplicateArgs
    assert state.query.path == ['edge3', 'edge1']
    assert state.query.kwargs == {'arg1': 'VAL1', 'arg2': 'val2'}
    assert state.query.node == cmd1
    assert_only_called(mock_methods.handle_error)

    # Case 10: Missing required args.
    handler.handle(state, 'edge3 edge1 arg2=val2')
    assert state.query.error == CommandErrors.MissingRequiredArgs(
        missing={'arg1'}, query=state.query
    )
    assert state.query.result is CommandErrors.MissingRequiredArgs

    assert_only_called(mock_methods.handle_error)

    # Case 11: Unrecognized args.
    handler.handle(state, 'edge3 edge1 arg1=val1 arg2=val2 arg3=val3')
    assert state.query.error == CommandErrors.UnrecognizedArgs(
        unrecognized={'arg3'}, query=state.query
    )
    assert state.query.result == CommandErrors.UnrecognizedArgs
    assert_only_called(mock_methods.handle_error)

    # Case 12: Parsing exception.
    handler.handle(state, 'edge3 edge1 arg1=val1 arg2=parse-fail')
    assert state.query.error == CommandErrors.ParseError(
        arg=arg2, value='parse-fail', error=parse_error, query=state.query
    )
    assert state.query.result is CommandErrors.ParseError
    assert_only_called(mock_methods.handle_error)

    # Case 13: Execution exception.
    handler.handle(state, 'edge3 edge1 arg1=cmd-fail arg2=val2')
    assert state.query.error == CommandErrors.ExecutionError(
        error=exe_error, query=state.query
    )
    assert state.query.result == CommandErrors.ExecutionError
    assert_only_called(mock_methods.handle_error, mock_methods.pre_execute)

    # Case 14: Unexpected exception.
    handler.handle(state, 'edge3 edge1 arg1=unexpected arg2=val2')
    assert state.query.error == CommandErrors.UnexpectedError(
        error=unexpected_error, query=state.query
    )
    assert state.query.result == CommandErrors.UnexpectedError
    assert_only_called(mock_methods.handle_error, mock_methods.pre_execute)

    # Case 15: No error occurs.
    state.query.error = None
    handler.handle(state, 'edge3 edge1 arg1=val1 arg2=val2')
    assert state.query.result == QueryResult.SUCCESS
    assert state.query.error is None
    assert state.query.node == cmd1
    assert state.query.path == ['edge3', 'edge1']
    assert_only_called(mock_methods.handle_success, mock_methods.pre_execute)


def test_default_handler(mock_messenger: Mock) -> None:
    # Test the default implementation of CommandHandler.
    mock_formatter = Mock(spec=QueryFormatter)
    mock_root = Mock(spec=CommandGroup)
    mock_security = Mock(spec=SecurityManager)
    handler = DefaultCommandHandler()
    state = DefaultCommandState(
        'App',
        mock_root,
        formatter=mock_formatter,
        messenger=mock_messenger,
        security_manager=mock_security
    )
    handler.send_user_msg(state, None)

    # When None is message, messenger should not be called.
    mock_messenger.assert_not_called()

    # Otherwise, messenger should be called with the message.
    handler.send_user_msg(state, 'msg')
    mock_messenger.assert_called_with('msg')

    # Have mock_formatter return a message that we can check was sent.
    mock_formatter.user_msg.return_value = 'other-msg'
    handler.send_query_msg(state)
    mock_formatter.user_msg.assert_called_with(state.query)
    mock_messenger.assert_called_with(mock_formatter.user_msg.return_value)

    # Check that each handle method calls send_query_msg with the state as an
    # argument.
    with mock.patch.object(
        handler, 'send_query_msg', autospec=True
    ) as mock_send_query_msg:
        for method in [
            handler.handle_cmd_help,
            handler.handle_error,
            handler.handle_general_help,
            handler.handle_group_help,
            handler.handle_help_not_found,
            handler.handle_success
        ]:
            # noinspection PyArgumentList
            method(state)
            mock_send_query_msg.assert_called_with(state)
            mock_send_query_msg.reset_mock()

    # Check that the security manager calls raise_if_cannot_execute on the state
    # for DefaultCommandHandler.pre_execute.
    handler.pre_execute(state)
    mock_security.raise_if_cannot_execute.assert_called_with(state)

    # Have mock_security raise a SecurityException and ensure it is transformed
    # into an execution error.
    error = SecurityError()
    mock_security.raise_if_cannot_execute.side_effect = error
    with enough.raises(CommandErrors.ExecutionError(
        error=error, query=state.query
    )):
        handler.pre_execute(state)
