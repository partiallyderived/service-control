"""This module contains commands native to keyword-commands."""
from collections import OrderedDict
from collections.abc import Callable, Mapping, Iterable

from enough import T

import keywordcommands.parsers as parsers
from keywordcommands.arg import Arg
from keywordcommands.command import ChainedExecutionError, Command
from keywordcommands.example import Example
from keywordcommands.parser import ParseFunction
from keywordcommands.role import CommandRole
from keywordcommands.security import RolesSecurityManager, SecurityErrors
from keywordcommands.state import UserState


def _assign_roles_cmd(
    *,
    cmd_desc: str,
    method: Callable[[RolesSecurityManager, Iterable[CommandRole], T, T], object],
    role_arg_desc: str,
    success_msg: str,
    user_arg_desc: str,
    user_parser: ParseFunction[T],
    examples: Iterable[Example] = (),
    users_format: str = 'names'
) -> Command[UserState[T]]:
    # Exploit shared logic between add_roles_cmd and remove_roles_cmd.
    def assign_roles(state: UserState[T], *, roles: Iterable[CommandRole], users: Iterable[T]) -> None:
        assert isinstance(state.security_manager, RolesSecurityManager)
        try:
            for u in users:
                method(state.security_manager, roles, state.user, u)
        except SecurityErrors.CannotAssign as e:
            # Foreseen exceptions should raise an ExecutionError.
            raise ChainedExecutionError(e)
        state.messenger(success_msg)

    roles_arg = Arg(role_arg_desc, 'roles', parsers.roles_parser)
    users_arg = Arg(
        user_arg_desc, 'users', parsers.delimited_parser(elem_name=users_format, fn=user_parser)
    )
    return Command(cmd_desc, assign_roles, args=[roles_arg, users_arg], examples=examples)


def add_roles_cmd(
    user_parser: ParseFunction[T], *, examples: Iterable[Example] = (), users_format: str = 'names'
) -> Command[UserState[T]]:
    """Uses the given user parser to create a :class:`.Command` which add roles to those users.

    :param user_parser: User parser to use.
    :param examples: Examples to configure command with.
    :param users_format: Description of the expected format for the users to parse.
    :return: The resulting command.
    """
    # noinspection PyTypeChecker
    return _assign_roles_cmd(
        cmd_desc='Add roles to users.',
        examples=examples,
        method=RolesSecurityManager.add_roles,
        role_arg_desc='Names of the roles to add.',
        success_msg='Roles added successfully.',
        user_arg_desc='Users to add roles to.',
        users_format=users_format,
        user_parser=user_parser
    )


def default_user_role_formatter(role_mapping: Mapping[object, Iterable[object]]) -> str:
    """Default function to use to format a user to role mapping or vice-versa for use in a user message.
    
    :param role_mapping: Mapping to format.
    :return: The resulting formatted string.
    """
    return '\n'.join(
        f'{key}: {", ".join(str(v) for v in values) if values else "<None>"}' for key, values in role_mapping.items()
    )


def remove_roles_cmd(
    user_parser: ParseFunction[T], users_format: str = 'names', examples: Iterable[Example] = ()
) -> Command[UserState[T]]:
    """Uses the given user parser to create a :class:`.Command` which remove roles from those users.

    :param user_parser: User parser to use.
    :param users_format: Description of the expected format for the users to parse.
    :param examples: Examples to configure command with.
    :return: The resulting command.
    """
    # noinspection PyTypeChecker
    return _assign_roles_cmd(
        cmd_desc='Remove roles from users.',
        examples=examples,
        method=RolesSecurityManager.remove_roles,
        role_arg_desc='Names of the roles to remove.',
        success_msg='Roles removed successfully.',
        user_arg_desc='Users to remove roles from.',
        users_format=users_format,
        user_parser=user_parser
    )


def show_role_users_cmd(
    *,
    examples: Iterable[Example] = (),
    formatter: Callable[[Mapping[CommandRole, Iterable[T]]], str] = default_user_role_formatter
) -> Command[UserState[T]]:
    """Creates a :class:`.Command` which shows the users belonging to specified roles.
    
    :param examples: Examples to configure command with.
    :param formatter: Formatter to use to format the user message.
    :return: The resulting command.
    """

    def show_users(state: UserState[T], *, roles: Iterable[CommandRole]) -> None:
        assert isinstance(state.security_manager, RolesSecurityManager)
        role_to_users = OrderedDict((role, state.security_manager.role_users(role)) for role in roles)
        msg = formatter(role_to_users)
        state.messenger(msg)

    roles_arg = Arg('Names of the roles to show users for.', 'roles', parsers.roles_parser)
    return Command('Shows users belonging to specified roles.', show_users, args=[roles_arg], examples=examples)


def show_user_roles_cmd(
    user_parser: ParseFunction[T],
    *,
    users_format: str = 'names',
    examples: Iterable[Example] = (),
    formatter: Callable[[Mapping[T, Iterable[CommandRole]]], str] = default_user_role_formatter
) -> Command[UserState]:
    """Uses the given user parser to create a :class:`.Command` which shows the roles belonging to those users.

    :param user_parser: User parser to use.
    :param users_format: Description of the expected format for the users to parse.
    :param examples: Examples to configure command with.
    :param formatter: Formatter to use to format the user role mapping.
    :return: The resulting command.
    """

    def show_roles(state: UserState[T], *, users: Iterable[T]) -> None:
        assert isinstance(state.security_manager, RolesSecurityManager)
        user_to_roles = OrderedDict((user, state.security_manager.user_roles(user)) for user in users)
        msg = formatter(user_to_roles)
        state.messenger(msg)
    
    users_arg = Arg(
        'Users to show roles for.', 'users', parsers.delimited_parser(elem_name=users_format, fn=user_parser)
    )
    return Command('Shows roles belonging to specified users.', show_roles, args=[users_arg], examples=examples)
