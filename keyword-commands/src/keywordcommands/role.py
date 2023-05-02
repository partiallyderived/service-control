from __future__ import annotations

from collections.abc import Iterable

from keywordcommands.command import Command
from keywordcommands.group import CommandGroup


class CommandRole:
    """A role to use to determine whether a user has access to a command."""

    #: Roles which may be assigned or removed by someone with this role.
    assignable_roles: set[CommandRole]

    #: Commands accessible with this role.
    cmds: set[Command]

    #: Name of this role.
    name: str

    def __init__(
        self,
        name: str,
        *,
        cmds: Iterable[Command] = (),
        groups: Iterable[CommandGroup] = (),
        bases: Iterable[CommandRole] = (),
        assignable_roles: Iterable[CommandRole] = (),
        may_assign_self: bool = False
    ) -> None:
        """Initialize this role using collections of
        :class:`Commands <.Command>`, :class:`CommandGroups <.CommandGroup>`,
        and sub-roles which are accessible from this role.

        :param name: Name to give to this role.
        :param cmds: Commands accessible to this role.
        :param groups: CommandGroups whose children are all accessible to this
            role, including other CommandGroups, recursively.
        :param bases: Roles whose accessible commands are accessible to this
            role and whose assignable roles are assignable by this role.
        :param assignable_roles: Roles which may be added or removed by someone
            with this role.
        :param may_assign_self: If ``True``, users with this role will be able
            to assign or remove it, otherwise they cannot unless
            ``CommandRole.assignable_roles`` is modified directly.
        """
        self.name = name
        self.cmds = set(cmds)
        for group in groups:
            for _, cmd in group.commands():
                self.cmds.add(cmd)
        self.assignable_roles = set(assignable_roles)
        for role in bases:
            self.cmds |= role.cmds
            self.assignable_roles |= role.assignable_roles
        if may_assign_self:
            self.assignable_roles.add(self)

    def __repr__(self) -> str:
        """Give a string representation of ``self`` suitable for programmers.

        :return: CommandRole(``self.name``).
        """
        return f'{type(self).__name__}({self.name})'

    def __str__(self) -> str:
        """Give a string representation of ``self`` suitable for users.

        :return: ``self.name``.
        """
        return self.name

    def may_assign(self, role: CommandRole) -> bool:
        """Determines whether this role is allowed to assign or remove the given
        role.

        :param role: The role to check.
        :return: ``True`` if the given role may be assigned or removed,
        ``False`` otherwise.
        """
        return role in self.assignable_roles

    def may_execute(self, cmd: Command) -> bool:
        """Determines whether this role has sufficient access to execute the
        given command.

        :param cmd: :class:`.Command` to determine access for.
        :return: ``True`` if this role has access to ``cmd``, ``False``
            otherwise.
        """
        return cmd in self.cmds
