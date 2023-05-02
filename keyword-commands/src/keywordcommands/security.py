from __future__ import annotations

import typing

from collections import defaultdict
from collections.abc import Iterable, Mapping, MutableMapping, MutableSet
from typing import Generic

from enough import EnumErrors, T

import keywordcommands.util as util
from keywordcommands._exceptions import KeywordCommandsError
from keywordcommands.role import CommandRole

if typing.TYPE_CHECKING:
    from keywordcommands import CommandState, UserState


class SecurityError(KeywordCommandsError):
    """Base class of security exceptions for keyword commands."""


class SecurityErrors(EnumErrors[SecurityError]):
    """Exception types raised in keywordcommands.security."""
    CannotAssign = (
        'User {user} does not have sufficient access to modify membership for'
            'the following roles: {roles}',
        ('roles', 'user')
    )
    CannotExecute = 'Insufficient access to execute "{path}"', 'state'
    DuplicateRoles = (
        'The following case-insensitive role names are given more than once: '
            '{", ".join(duplicated)}',
        'duplicated'
    )
    NoSuchRole = 'No role named {name}', 'name'
    UnrecognizedRoles = (
        'The following roles are specified in the values of user_to_roles but'
            'not in roles: {", ".join(role.name for role in unrecognized)}',
        'unrecognized'
    )
    UserCannotExecute = (
        'User {state.user} does not have sufficient access to execute "{path}"',
        'state'
    )

    @property
    def path(cls) -> str:
        return util.expand_path(cls.state.query.path)


class SecurityManager:
    """Determines whether the execution of a command would violate security
    configurations.
    """
    def _make_exception(self, state: CommandState) -> SecurityError:
        # Make the exception to raise if there is insufficient access to execute
        # a command.
        return SecurityErrors.CannotExecute(state=state)

    def may_execute(self, state: CommandState) -> bool:
        """Determine whether the command to be executed with the given state
        would violate security configurations.

        :param state: Current command state.
        :return: ``True`` if the command may be executed, ``False`` otherwise.
        """
        return True

    def raise_if_cannot_execute(self, state: CommandState) -> None:
        """Raise an exception if executing the command with the given state
        would violate security configurations.

        :param state: Current command state.
        :raise SecurityException: If ``not self.may_execute(state)``.
        """
        if not self.may_execute(state):
            raise self._make_exception(state)


class RolesSecurityManager(SecurityManager, Generic[T]):
    """Determines whether the execution of a command would violate security
    configurations by checking if the user has a role allowing access.
    """

    #: Mapping from role names to the corresponding role.
    name_to_role: MutableMapping[str, CommandRole]

    #: Mapping from roles to the users which have that role.
    role_to_users: defaultdict[CommandRole, set[T]]

    #: Mapping from user objects to the roles they have access to.
    user_to_roles: MutableMapping[T, MutableSet[CommandRole]]

    @staticmethod
    def _role_users(
        user_to_roles: Mapping[T, MutableSet[CommandRole]]
    ) -> defaultdict[CommandRole, set[T]]:
        # From the given mapping of users to their roles, create the inverse
        # mapping from roles to the users that have that role.
        role_to_users = defaultdict(set)
        for user, roles in user_to_roles.items():
            for role in roles:
                role_to_users[role].add(user)
        return role_to_users

    def _add_role(self, role: CommandRole, user: T) -> None:
        # Add a role to a user.
        self.user_to_roles.setdefault(user, set()).add(role)
        self.role_to_users[role].add(user)

    def _assign_roles(
        self,
        roles: Iterable[CommandRole],
        executor: T,
        subject: T,
        is_remove: bool
    ) -> None:
        # Logic for add and remove is almost the same, so put logic in shared
        # function.
        insufficient_access = {
            role for role in roles if not self.may_assign_role(role, executor)
        }
        if insufficient_access:
            raise SecurityErrors.CannotAssign(
                roles=insufficient_access, user=executor
            )
        if is_remove:
            for role in roles:
                self._remove_role(role, subject)
        else:
            for role in roles:
                self._add_role(role, subject)

    def _make_exception(self, state: UserState) -> SecurityError:
        # Use this exception so we have access to user.
        raise SecurityErrors.UserCannotExecute(state=state)

    def _remove_role(self, role: CommandRole, user: T) -> None:
        # Remove a role from a user.
        try:
            self.user_to_roles.setdefault(user, set()).remove(role)
        except KeyError:
            pass
        try:
            self.role_to_users[role].remove(user)
        except KeyError:
            pass

    def __init__(
        self,
        roles: Iterable[CommandRole],
        *,
        user_to_roles: MutableMapping[T, MutableSet[CommandRole]] | None = None
    ) -> None:
        """Initialize this security manager with the given role mappings.

        :param roles: The roles this security manager will recognize. Must have
            unique case-insensitive names.
        :param user_to_roles: Optional mapping from user objects to the set of
            roles that user has to init with.
        :raise SecurityError: If any roles in ``roles`` have the same name, or
            if any roles are specified in ``user_to_roles.values()`` but not
            ``roles``.
        """
        name_to_roles = defaultdict(set)
        [name_to_roles[role.name].add(role) for role in roles]
        dup_names = {
            name for name, roles in name_to_roles.items() if len(roles) > 1
        }
        if dup_names:
            raise SecurityErrors.DuplicateRoles(duplicated=dup_names)
        self.name_to_role = {role.name: role for role in roles}
        self.user_to_roles = user_to_roles or {}
        unrecognized_roles = {
            role for role_set in self.user_to_roles.values()
            for role in role_set if role.name not in name_to_roles
        }
        if unrecognized_roles:
            raise SecurityErrors.UnrecognizedRoles(
                unrecognized=unrecognized_roles
            )
        self.role_to_users = self._role_users(self.user_to_roles)

    def add_roles(
        self, roles: Iterable[CommandRole], executor: T, subject: T
    ) -> None:
        """Attempt to add one or more roles to a user.

        :param roles: Roles to add.
        :param executor: User who is attempting to add the role.
        :param subject: User for whom the role is being added.
        :raise SecurityError: If ``executor`` does not have sufficient access to
            assign the given roles.
        """
        self._assign_roles(roles, executor, subject, is_remove=False)

    def may_assign_role(self, role: CommandRole, user: T) -> bool:
        """Determines whether the given user may assign or remove the given
        role.

        :param role: Role to check.
        :param user: User to check for.
        :return: ``True`` if ``executor`` may assign the role specified by
            ``role_name``, ``False`` otherwise.
        """
        user_roles = self.user_to_roles.get(user, set())
        return any(r.may_assign(role) for r in user_roles)

    def may_execute(self, state: UserState) -> bool:
        """Determines whether a user has sufficient access to execute a
        :class:`.Command`. Does not necessarily imply that the user has
        sufficient access to completely carry out the command
        (i.e., when assigning or removing permissions when they do not have
        access to).

        :param state: The state to use to check access.
        :return: ``True`` if the user has sufficient access, ``False``
            otherwise.
        """
        return any(
            r.may_execute(state.query.cmd)
            for r in self.user_to_roles.setdefault(state.user, set())
        )

    def remove_roles(
        self, roles: Iterable[CommandRole], executor: T, subject: T
    ) -> None:
        """Attempt to remove one or more roles for a user.

        :param roles: Roles to remove.
        :param executor: User who is attempting to remove the roles.
        :param subject: User for whom the roles are to be removed.
        """
        self._assign_roles(roles, executor, subject, is_remove=True)

    def role(self, name: str) -> CommandRole:
        """Get the role corresponding to the given name.

        :param name: Name of role to get.
        :return: The retrieved role.
        :raise SecurityError: If the role does not exist.
        """
        role = self.name_to_role.get(name.lower())
        if role is None:
            raise SecurityErrors.NoSuchRole(name=name)
        return role

    def role_users(self, role: CommandRole) -> set[T]:
        """Get the users who have been assigned the given role.

        :param role: Role to get assigned users for.
        :return: The assigned users.
        """
        return self.role_to_users[role]

    def user_roles(self, user: T) -> MutableSet[CommandRole]:
        """Get the roles assigned to the given user.

        :param user: User to get assigned roles for.
        :return: The resulting roles.
        """
        return self.user_to_roles.setdefault(user, set())
