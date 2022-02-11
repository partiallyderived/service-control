import unittest.mock as mock
from unittest.mock import Mock

import enough as br

from keywordcommands import Command, CommandGroup
from keywordcommands.exceptions import GroupInitErrors


def test_check_for_dupes() -> None:
    # Test CommandGroup._check_for_dupes, which should check a given mapping for any case-insensitive duplicate keys.

    # Should succeed.
    CommandGroup._check_for_dupes({'a': Mock(spec=Command | CommandGroup), 'b': Mock(spec=Command | CommandGroup)})

    # Should fail.
    with br.raises(GroupInitErrors.DuplicateEdges(duplicated={'a'})):
        CommandGroup._check_for_dupes({'a': Mock(spec=Command | CommandGroup), 'A': Mock(spec=Command | CommandGroup)})


def test_malformed_edges() -> None:
    # Test CommandGroup._malformed_edges, which should indicate which strings from a collection contain invalid
    # characters.
    CommandGroup._check_malformed_edges({'asdf', 'fdsa'})
    with br.raises(GroupInitErrors.MalformedEdges(malformed={'$asdf'})):
        CommandGroup._check_malformed_edges({'$asdf', 'fdsa'})


def test_group(cmd_no_args: Command, cmd1: Command, cmd2: Command) -> None:
    # Test the CommandGroup methods __init__, commands, find, and tree.

    # Mock check methods to make sure they're called.
    with mock.patch.multiple(CommandGroup, _check_for_dupes=mock.DEFAULT, _check_malformed_edges=mock.DEFAULT) as mocks:
        group = CommandGroup('Group description', edge1=cmd1, edge2=cmd2)
        assert group.description == 'Group description'
        mocks['_check_for_dupes'].assert_called()
        mocks['_check_malformed_edges'].assert_called()

    # group.tree should contain direct paths.
    assert group.tree() == {'edge1': cmd1, 'edge2': cmd2}

    # group.find should be able to find the commands, or itself with an empty path.
    assert group.find([]) == group
    assert group.find(['edge1']) == cmd1
    assert group.find(['edge2']) == cmd2

    # Non-paths.
    assert group.find(['edge3']) is None
    assert group.find(['edge1', 'edge1.5']) is None

    # Test group.commands(), which should give a list of (path, cmd) pairs in alphabetical order.
    assert group.commands() == [(['edge1'], cmd1), (['edge2'], cmd2)]

    # paths() should include the group itself.
    assert group.paths() == [([], group), (['edge1'], cmd1), (['edge2'], cmd2)]

    # Make another group with this group as a path.
    group2 = CommandGroup('Another group', edge1=cmd_no_args, edge3=group)
    assert group2.tree() == {'edge1': cmd_no_args, 'edge3': group}

    assert group2.find(['edge1']) == cmd_no_args
    assert group2.find(['edge1', 'edge1']) is None
    assert group2.find(['edge3']) == group
    assert group2.find(['edge3', 'edge1']) == cmd1
    assert group2.find(['edge3', 'edge2']) == cmd2
    assert group2.find(['edge3', 'edge3']) is None

    # commands() should find all commands, even those which are not direct edges.
    assert group2.commands() == [(['edge1'], cmd_no_args), (['edge3', 'edge1'], cmd1), (['edge3', 'edge2'], cmd2)]

    # paths() should find all commands and command groups.
    assert group2.paths() == [
        ([], group2),
        (['edge1'], cmd_no_args),
        (['edge3'], group),
        (['edge3', 'edge1'], cmd1),
        (['edge3', 'edge2'], cmd2)
    ]
