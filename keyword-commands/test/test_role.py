from keywordcommands import Command, CommandGroup, CommandRole


def test_may_execute(
    cmd_no_args: Command,
    cmd1: Command,
    cmd2: Command,
    cmd3: Command,
    cmd4: Command,
    group1: CommandGroup,
    group2: CommandGroup,
    group3: CommandGroup
) -> None:
    # Test CommandRole.may_execute and the __init__ args relevant to it.
    # First, establish that test_role.may_execute(cmd) returns True whenever cmd in test_role.cmds.

    # Create an empty role first.
    test_role = CommandRole('test')
    assert test_role.assignable_roles == set()
    assert test_role.cmds == set()
    assert test_role.name == 'test'
    assert str(test_role) == test_role.name
    for cmd in [cmd_no_args, cmd1, cmd2]:
        assert not test_role.may_execute(cmd)

    # Try with different combinations of commands.
    all_cmds = {cmd_no_args, cmd1, cmd2}
    for cmds in [{cmd_no_args}, {cmd1}, {cmd2}, {cmd1, cmd2}, all_cmds]:
        test_role.cmds = cmds
        for cmd in cmds:
            assert test_role.may_execute(cmd)
        for cmd in all_cmds - cmds:
            assert not test_role.may_execute(cmd)

    # Now there is no need to use may_execute for each command we want to verify may execute. We can instead just verify
    # the CommandRole.cmds is exactly the set of commands that are expected to executable.
    assert CommandRole('', cmds=[cmd1, cmd2]).cmds == {cmd1, cmd2}
    assert CommandRole('', cmds=[cmd1, cmd2, cmd3, cmd4]).cmds == {cmd1, cmd2, cmd3, cmd4}
    assert CommandRole('', groups=[group1]).cmds == {cmd1, cmd2}
    assert CommandRole('', groups=[group2]).cmds == {cmd_no_args, cmd1, cmd2}
    assert CommandRole('', groups=[group1, group3]).cmds == {cmd1, cmd2, cmd3, cmd4}
    assert CommandRole('', cmds=[cmd1, cmd3], groups=[group1]).cmds == {cmd1, cmd2, cmd3}
    assert CommandRole('', cmds=[cmd_no_args], groups=[group1, group3]).cmds == {cmd_no_args, cmd1, cmd2, cmd3, cmd4}
    assert CommandRole('', bases=[CommandRole('', cmds=[cmd1, cmd2])]).cmds == {cmd1, cmd2}
    assert CommandRole('', bases=[CommandRole('', groups=[group1, group2])]).cmds == {cmd_no_args, cmd1, cmd2}
    assert CommandRole('', bases=[CommandRole('', cmds=[cmd1, cmd2]), CommandRole('', groups=[group3])]).cmds == {
        cmd1, cmd2, cmd3, cmd4
    }
    assert CommandRole('', cmds=[cmd1, cmd2], bases=[CommandRole('', groups=[group3])]).cmds == {
        cmd1, cmd2, cmd3, cmd4
    }
    assert CommandRole('', cmds=[cmd_no_args], groups=[group1], bases=[CommandRole('', groups=[group3])]).cmds == {
        cmd_no_args, cmd1, cmd2, cmd3, cmd4
    }


def test_may_assign(role_empty: CommandRole, role1: CommandRole, role2: CommandRole) -> None:
    # Test CommandRole.may_assign and its relevant constructor argument.
    # Ensure that bases does not determine assignability.
    all_roles = [role_empty, role1, role2]
    role_no_assign = CommandRole('', bases=[role_empty])
    assert not role_no_assign.may_assign(role_empty)
    assert not role_no_assign.may_assign(role_no_assign)

    # Now use the correct constructor argument.
    role_with_assign = CommandRole('', assignable_roles=all_roles)
    for role in all_roles:
        assert role_with_assign.may_assign(role)
    assert not role_with_assign.may_assign(role_with_assign)

    # True with may_assign_self=True.
    role = CommandRole('', assignable_roles=[role_empty, role2], may_assign_self=True)
    assert role.may_assign(role_empty)
    assert not role.may_assign(role1)
    assert role.may_assign(role2)
    assert role.may_assign(role)

    # While base roles are not necessarily assignable, a role will inherit the assignable roles of its bases.
    higher_role = CommandRole('', bases=[role])
    assert higher_role.may_assign(role_empty)
    assert higher_role.may_assign(role2)
