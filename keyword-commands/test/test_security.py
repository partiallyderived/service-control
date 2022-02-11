import enough as br

from keywordcommands import Command, CommandRole, RolesSecurityManager
from keywordcommands.exceptions import SecurityErrors

from conftest import StrUserState


def test_roles_security_manager(
    cmd1: Command,
    cmd2: Command,
    cmd3: Command,
    cmd4: Command,
    role_empty,
    role1: CommandRole,
    role2: CommandRole,
    user_state: StrUserState
) -> None:
    # Test the methods of RolesSecurityManager.

    # __init__ with empty args.
    manager = RolesSecurityManager(())
    assert manager.name_to_role == {}
    assert manager.role_to_users == {}
    assert manager.user_to_roles == {}
    assert manager.user_roles('user1') == set()  # Using previously unspecified users is allowed.

    # Using unspecified roles is not allowed.
    with br.raises(SecurityErrors.NoSuchRole(name='role1')):
        manager.role('role1')

    # __init__ where duplicate role names are given for roles.
    role_empty2 = CommandRole('empty')
    role1_2 = CommandRole('role1')
    with br.raises(SecurityErrors.DuplicateRoles(duplicated={'empty', 'role1'})):
        RolesSecurityManager(roles=[role_empty, role1, role2, role_empty2, role1_2])

    # __init__ where user_to_roles has roles not given for roles.
    with br.raises(SecurityErrors.UnrecognizedRoles(unrecognized={role1, role2})):
        RolesSecurityManager(roles=[role_empty], user_to_roles={'user1': {role1}, 'user2': {role2}})

    # Nontrivial __init__.
    manager = RolesSecurityManager(
        roles=[role1, role2],
        user_to_roles={'user1': set(), 'user2': {role1}, 'user3': {role2}, 'user4': {role1, role2}}
    )
    assert manager.name_to_role == {'role1': role1, 'role2': role2}
    assert manager.role_to_users == {role1: {'user2', 'user4'}, role2: {'user3', 'user4'}}
    assert manager.user_to_roles == {'user1': set(), 'user2': {role1}, 'user3': {role2}, 'user4': {role1, role2}}

    # Test RolesSecurityManager.role_users.
    for role, users in manager.role_to_users.items():
        assert manager.role_users(role) == users

    # Test RolesSecurityManager.user_roles.
    for user, roles in manager.user_to_roles.items():
        assert manager.user_roles(user) == roles

    # Test RolesSecurityManager.role.
    assert manager.role('role1') == role1
    assert manager.role('rOLE1') == role1
    assert manager.role('role2') == role2
    with br.raises(SecurityErrors.NoSuchRole(name='empty')):
        manager.role('empty')

    # Test RolesSecurityManager.may_execute.
    all_cmds = [cmd1, cmd2, cmd3, cmd4]
    query = user_state.query
    query.node = cmd1
    user_state.user = 'user1'
    for cmd in all_cmds:
        query.node = cmd
        assert not manager.may_execute(user_state)

    user_state.user = 'user2'
    query.node = cmd1
    assert manager.may_execute(user_state)

    query.node = cmd2
    assert manager.may_execute(user_state)

    query.node = cmd3
    assert not manager.may_execute(user_state)

    query.node = cmd4
    assert not manager.may_execute(user_state)

    user_state.user = 'user4'
    for cmd in all_cmds:
        query.node = cmd
        assert manager.may_execute(user_state)

    # Test RolesSecurityManager.may_assign_role.
    all_roles = [role_empty, role1, role2]
    for role in all_roles:
        # User 1 has no roles and cannot assign anything.
        assert not manager.may_assign_role(role, 'user1')
        if role == role_empty:
            # User 2 has role "role1", which can only assign role_empty.
            assert manager.may_assign_role(role, 'user2')
        else:
            assert not manager.may_assign_role(role, 'user2')
        # User 3 and user 4 both have role2, which can assign all three roles.
        assert manager.may_assign_role(role, 'user3')
        assert manager.may_assign_role(role, 'user4')

    # Test RolesSecurityManager.add_roles.
    with br.raises(SecurityErrors.CannotAssign(roles={role1, role2}, user='user2')):
        manager.add_roles([role_empty, role1, role2], 'user2', 'user5')
    assert not manager.user_roles('user5')

    manager.add_roles([role1, role2], 'user4', 'user5')
    assert manager.user_roles('user5') == {role1, role2}

    # Test RolesSecurityManager.remove_roles.
    with br.raises(SecurityErrors.CannotAssign(roles={role1, role2}, user='user2')):
        manager.remove_roles([role_empty, role1, role2], 'user2', 'user5')
    assert manager.user_roles('user5') == {role1, role2}

    manager.remove_roles([role_empty, role2], 'user4', 'user5')
    assert manager.user_roles('user5') == {role1}
