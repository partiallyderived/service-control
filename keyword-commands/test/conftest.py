from collections.abc import Callable
from unittest.mock import Mock

import pytest

from keywordcommands import (
    Arg,
    Command,
    CommandGroup,
    CommandRole,
    CommandState,
    Example,
    RolesSecurityManager,
    UserState
)


# Trivial UserState implementation.
class StrUserState(UserState[str]):
    _user: str

    def __init__(self) -> None:
        super().__init__('', CommandGroup(''))
        self._user = ''

    @property
    def user(self) -> str:
        return self._user

    @user.setter
    def user(self, new_user: str) -> None:
        self._user = new_user


# Arguments to use for testing.
@pytest.fixture
def arg1() -> Arg[str]:
    return Arg('Argument 1.', 'arg1')


@pytest.fixture
def arg2() -> Arg[str]:
    return Arg('Argument 2.', 'arg2')


@pytest.fixture
def arg3() -> Arg[str]:
    return Arg('Argument 3.', 'arg3')


@pytest.fixture
def arg4() -> Arg[str]:
    return Arg('Argument 4.', 'arg4')


# Examples to use for testing.
@pytest.fixture
def examples() -> list[Example]:
    return [
        Example('Example 1', {'arg1': 'val1', 'arg2': 'val2'}, unchecked=False),
        Example('Example 2', {'arg1': 'val3'}, unchecked=True)
    ]


# Examples to use when checking their functionality is irrelevant.
@pytest.fixture
def void_examples() -> list[Example]:
    return [Example('', {}, unchecked=True), Example('', {}, unchecked=True)]


# Functions the commands will use.
# noinspection PyUnusedLocal
def cmd1_fn(state: CommandState, *, arg1: str, arg2: str = 'asdf') -> None: pass
# noinspection PyUnusedLocal
def cmd2_fn(state: CommandState, *, arg3: str, arg4: str = 'fdsa') -> None: pass


# Commands to use for testing.
# Command that has no arguments.
@pytest.fixture
def cmd_no_args() -> Command:
    return Command('Command.', lambda state: None)


@pytest.fixture
def cmd1(arg1: Arg[str], arg2: Arg[str], examples: list[Example]) -> Command:
    return Command('Command 1.', cmd1_fn, args=[arg1, arg2], examples=examples)


@pytest.fixture
def cmd2(arg3: Arg[str], arg4: Arg[str]) -> Command:
    return Command('Command 2.', cmd2_fn, args=[arg3, arg4])


@pytest.fixture
def cmd3() -> Command:
    return Command('Command 3.', lambda state: None)


@pytest.fixture
def cmd4() -> Command:
    return Command('Command 4.', lambda state: None)


# Command groups to use for testing.
# CommandGroup with no edges.
@pytest.fixture
def group_empty() -> CommandGroup:
    return CommandGroup('Group.')


@pytest.fixture
def group1(cmd1: Command, cmd2: Command) -> CommandGroup:
    return CommandGroup('Group 1.', edge1=cmd1, edge2=cmd2)


@pytest.fixture
def group2(cmd_no_args: Command, group1: CommandGroup) -> CommandGroup:
    # Note this group's dependence on another group.
    return CommandGroup('Group 2.', edge1=cmd_no_args, edge3=group1)


@pytest.fixture
def group3(cmd3: Command, cmd4: Command) -> CommandGroup:
    return CommandGroup('Group 3.', edge3=cmd3, edge4=cmd4)


# CommandRoles to use for testing.
# CommandRole with no commands.
@pytest.fixture
def role_empty() -> CommandRole:
    return CommandRole('empty')


@pytest.fixture
def role1(cmd1: Command, cmd2: Command, role_empty: CommandRole) -> CommandRole:
    return CommandRole(
        'role1', cmds=[cmd1, cmd2], assignable_roles=[role_empty]
    )


@pytest.fixture
def role2(
    cmd3: Command, cmd4: Command, role_empty: CommandRole, role1: CommandRole
) -> CommandRole:
    return CommandRole(
        'role2',
        cmds=[cmd3, cmd4],
        assignable_roles=[role_empty, role1],
        may_assign_self=True
    )


# RolesSecurityManager to use for testing.
@pytest.fixture
def security_manager(
    role_empty: CommandRole, role1: CommandRole, role2: CommandRole
) -> RolesSecurityManager:
    return RolesSecurityManager(
        roles=[role_empty, role1, role2],
        user_to_roles={
            'user1': set(),
            'user2': {role1},
            'user3': {role_empty, role1, role2}
        }
    )


# UserState to use for testing.
@pytest.fixture
def user_state(security_manager: RolesSecurityManager) -> StrUserState:
    state = StrUserState()
    state.security_manager = security_manager
    return state


# Useful Mocks.
# Mocked messenger for user_state.
@pytest.fixture
def mock_messenger(user_state: UserState) -> Mock:
    user_state.messenger = Mock(spec=Callable)
    return user_state.messenger
