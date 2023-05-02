import unittest.mock as mock
from collections import OrderedDict
from collections.abc import Callable
from unittest.mock import Mock

import enough

from keywordcommands import (
    CommandRole, Example, Parser, RolesSecurityManager, commands
)
from keywordcommands.exceptions import (
    ChainedExecutionError, CommandErrors, SecurityErrors
)

from conftest import StrUserState


def test_assign_roles_cmd(
    user_state: StrUserState,
    role_empty: CommandRole,
    role1: CommandRole,
    role2: CommandRole,
    void_examples: list[Example],
    mock_messenger: Mock
) -> None:
    # Test commands._assign_roles_cmd, a helper method containing the core logic
    # for add_roles_cmd and remove_roles_cmd.

    mock_method = Mock(spec=Callable)
    roles = [role_empty, role1, role2]

    # noinspection PyTypeChecker
    cmd = commands._assign_roles_cmd(
        cmd_desc='Command description.',
        examples=void_examples,
        method=mock_method,
        role_arg_desc='Role arg description.',
        success_msg='Success message.',
        user_arg_desc='User arg description.',
        users_format='users_format',
        user_parser=Parser.DEFAULT
    )
    assert cmd.arg('roles').description == 'Role arg description.'
    assert cmd.arg('users').description == 'User arg description.'
    assert cmd.arg(
        'users'
    ).parser.expected_format == 'Comma-separated list of users_format'
    assert cmd.args.keys() == {'roles', 'users'}
    assert cmd.description == 'Command description.'
    assert cmd.examples == void_examples

    unparsed = {
        'roles': f'{role_empty},{role1},{role2}',
        'users': 'user1,user2,user3'
    }
    parsed = cmd.parse(user_state, unparsed)
    assert parsed == {
        'roles': roles,
        'users': ['user1', 'user2', 'user3']
    }

    user_state.user = 'user'
    cmd(user_state, parsed)
    manager = user_state.security_manager
    mock_method.assert_has_calls([
        mock.call(manager, roles, 'user', 'user1'),
        mock.call(manager, roles, 'user', 'user2'),
        mock.call(manager, roles, 'user', 'user3')
    ])
    mock_messenger.assert_called_with('Success message.')

    # Make sure a SecurityErrors.CANNOT_ASSIGN leads to
    # ChainedExecutionException being raised.
    # Need path and text to be set for this since the exception uses it to
    # format a message.
    user_state.query.path = []
    user_state.query.text = ''
    error = SecurityErrors.CannotAssign(roles=roles, user='user')
    mock_method.side_effect = error
    with enough.raises(CommandErrors.ExecutionError(
        error=ChainedExecutionError(error), query=user_state.query)
    ):
        cmd(user_state, parsed)


def test_add_roles_cmd(void_examples: list[Example]) -> None:
    # Just test that _assign_roles_cmd is properly called.
    with mock.patch(
        'keywordcommands.commands._assign_roles_cmd'
    ) as mock_helper:
        assert commands.add_roles_cmd(
            user_parser=Parser.DEFAULT,
            examples=void_examples,
            users_format='users_format'
        ) == mock_helper.return_value
        kwargs = mock_helper.call_args.kwargs
        # Checking default messages is frivolous and error-prone, check other
        # args instead.
        assert kwargs['examples'] == void_examples
        assert kwargs['method'] == RolesSecurityManager.add_roles
        assert kwargs['user_parser'] == Parser.DEFAULT


def test_default_user_role_formatter(
    role_empty: CommandRole, role1: CommandRole, role2: CommandRole
) -> None:
    # Test commands.default_user_role_formatter, which lists the roles for each
    # user on a separate line, or vice-versa.
    # This message precedes the list of roles/users.
    assert commands.default_user_role_formatter(OrderedDict(
        [('user1', []), ('user2', [role_empty]), ('user3', [role1, role2])]
    )) == (
        f'user1: <None>\n'
        f'user2: {role_empty}\n'
        f'user3: {role1}, {role2}'
    )

    assert commands.default_user_role_formatter(OrderedDict(
        [(role_empty, []), (role1, ['user1']), (role2, ['user2', 'user3'])]
    )) == (
        f'{role_empty}: <None>\n'
        f'{role1}: user1\n'
        f'{role2}: user2, user3'
    )


def test_remove_roles_cmd(void_examples: list[Example]) -> None:
    # Just test that _assign_roles_cmd is properly called.
    with mock.patch(
        'keywordcommands.commands._assign_roles_cmd'
    ) as mock_helper:
        assert commands.remove_roles_cmd(
            user_parser=Parser.DEFAULT,
            examples=void_examples,
            users_format='users_format'
        ) == mock_helper.return_value
        kwargs = mock_helper.call_args.kwargs

        # Checking default messages is frivolous and error-prone, check other
        # args instead.
        assert kwargs['examples'] == void_examples
        assert kwargs['method'] == RolesSecurityManager.remove_roles
        assert kwargs['user_parser'] == Parser.DEFAULT


def test_show_role_users_cmd(
    user_state: StrUserState,
    role_empty: CommandRole,
    role1: CommandRole,
    role2: CommandRole,
    void_examples: list[Example],
    mock_messenger: Mock
) -> None:
    # Test that commands.show_role_users_cmd creates a command that prints the
    # users assigned with the specified roles.
    mock_formatter = Mock(spec=Callable)
    cmd = commands.show_role_users_cmd(
        examples=void_examples, formatter=mock_formatter
    )
    assert cmd.args.keys() == {'roles'}
    parsed = cmd.parse(user_state, {'roles': f'{role_empty},{role1},{role2}'})
    assert parsed == {'roles': [role_empty, role1, role2]}
    cmd(user_state, parsed)
    mock_formatter.assert_called_with(
        {role_empty: {'user3'}, role1: {'user2', 'user3'}, role2: {'user3'}}
    )
    mock_messenger.assert_called_with(mock_formatter.return_value)


def test_show_user_roles_cmd(
    user_state: StrUserState,
    role_empty: CommandRole,
    role1: CommandRole,
    role2: CommandRole,
    void_examples: list[Example],
    mock_messenger: Mock
) -> None:
    # Test that commands.show_user_roles_cmd creates a command that prints the
    # roles assign to the specified users.
    mock_formatter = Mock(spec=Callable)
    cmd = commands.show_user_roles_cmd(
        examples=void_examples,
        formatter=mock_formatter,
        users_format='users_format',
        user_parser=Parser.DEFAULT
    )
    assert cmd.arg(
        'users'
    ).parser.expected_format == 'Comma-separated list of users_format'
    assert cmd.args.keys() == {'users'}
    parsed = cmd.parse(user_state, {'users': 'user1,user2,user3'})
    assert parsed == {'users': ['user1', 'user2', 'user3']}
    cmd(user_state, parsed)
    mock_formatter.assert_called_with(
        {'user1': set(), 'user2': {role1}, 'user3': {role_empty, role1, role2}}
    )
