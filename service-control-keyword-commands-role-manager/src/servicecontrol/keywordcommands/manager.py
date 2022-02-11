from collections.abc import Callable, Iterable, MutableMapping, MutableSet
from typing import Final

import enough as br
from enough import JSONType, T
from keywordcommands import Command, CommandGroup, CommandRole, RolesSecurityManager

from servicecontrol.core import Service
from servicecontrol.tools.data import DataDict


class PersistentRolesSecurityManager(RolesSecurityManager):
    """:class:`.RolesSecurityManager` which executes a callback function whenever it is modified."""

    def __init__(
        self,
        mutate_hook: Callable[[], object],
        roles: Iterable[CommandRole],
        *,
        user_to_roles: MutableMapping[T, MutableSet[CommandRole]] | None = None
    ) -> None:
        """Initialize this security manager with a mutation hook which is called whenever roles are added or removed.

        :param mutate_hook: Function to be called whenever roles are added or removed.
        :param roles: Roles to recognize.
        :param user_to_roles: Optional mapping from users to the set of roles assigned to them. May be modified later.
        """
        super().__init__(roles, user_to_roles=user_to_roles)
        self.mutate_hook = mutate_hook

    def _assign_roles(self, roles: Iterable[CommandRole], executor: T, subject: T, is_remove: bool) -> None:
        # Call the mutate hook after assigning roles.
        super()._assign_roles(roles, executor, subject, is_remove)
        self.mutate_hook()


class KeywordCommandsRoleManagerService(Service):
    """Service which acts as a role manager for keyword commands"""

    EXPORTS: Final[frozenset[str]] = frozenset('keyword_commands_role_manager')
    NAME: Final[str] = 'keyword-commands-role-manager'
    SCHEMA: Final[JSONType] = {
        'description': 'Config for KeywordCommandsRoleManagerService.',
        'type': 'object',
        'properties': {
            'root': {
                'description': 'Fully-qualified name of root command group to use.',
                'type': 'string',
                'pattern': r'^[a-zA-Z_][a-zA-Z0-9_.]*$'
            },
            'roles': {
                'description': 'Roles to recognize.',
                'type': 'object',
                'properties': {
                    'access': {
                        'description': 'Commands and CommandGroups which may be executed by a user with this role.',
                        'type': 'array',
                        'items': {
                            'description': (
                                'Name of command or group this role has access to. The name is the same as the '
                                'space-separated path to the command.'
                            ),
                            'type': 'string',
                            'pattern': r'^[a-zA-Z0-9\-](|[a-zA-Z0-9\- ]*[a-zA-Z0-9\-])$'
                        }
                    },
                    'bases': {
                        'description': 'Roles which this role inherits the permissions of.',
                        'type': 'array',
                        'items': {
                            'description': 'Name of base role.',
                            'type': 'string'
                        }
                    },
                    'may-assign': {
                        'description': (
                            'Roles which may be assigned by users with this role. May include the role itself.'
                        ),
                        'type': 'array',
                        'items': {
                            'description': 'Name of role which may be assigned.',
                            'type': 'string'
                        }
                    }
                },
                'additionalProperties': False
            }
        },
        'additionalProperties': False,
        'required': ['roles', 'root']
    }

    # Data dictionary associated with this service.
    _data: DataDict

    #: The exported :class:`.PersistentRolesManager

    def __init__(self, config: JSONType, data: DataDict) -> None:
        """Initializes the service with the given config.
        
        :param config: Config to initialize with.
        :param data: Data dictionary to save role assignments to and load role assignments from.
        :raise ImportError: If the root command group failed to be imported.
        :raise TypeError: If an imported root command group is not an instance of :class:`.CommandGroup`.
        :raise ValueError: If there are mutually dependent roles according to the :code:`bases` or :code:`may-assign`
            configuration, or if there are names specified in :code:`access` which are not paths to commands or groups
            under :code:`root`. A role may have itself listed under :code:`may-assign`.
        """
        super().__init__(config)
        self._data = data
        root_fqln = config['root']
        root = br.typed_import(root_fqln, CommandGroup)
        path_to_node = {}
        for path, node in root.paths():
            path_to_node[' '.join(path)] = node
        roles = config['roles']

        # Check if any roles reference nodes not derived from root.
        unrecognized = set()
        for role, props in roles.items():
            for accessible in props.get('access'):
                if accessible not in path_to_node:
                    unrecognized.add(accessible)
        if unrecognized:
            raise ValueError(
                f'The following names are not paths to commands or groups under the root group {root_fqln}: '
                    f'{", ".join(unrecognized)}'
            )
        role_dependency_map = {}
        self_assignable = set()
        for role, props in roles.items():
            # Before creating CommandRole objects, we need to determine a creation order based on "bases" and
            # "may-assign".
            dependencies = set(props.get('bases', []) + props.get('may-assign'))
            if role in dependencies:
                # Use may_assign_self parameter and remove from dependency map for roles that may assign themselves.
                dependencies.remove(role)
                self_assignable.add(role)
        role_stages = br.dag_stages(role_dependency_map)
        name_to_role = {}
        for stage in role_stages:
            for role in stage:
                props = roles[role]
                cmds = []
                groups = []
                for accessible in props.get('access', []):
                    node = path_to_node[accessible]
                    if isinstance(node, Command):
                        cmds.append(node)
                    else:
                        groups.append(node)
                bases = [name_to_role[base] for base in props.get('bases', [])]
                assignable = [name_to_role[r] for r in props.get('may-assign') if r != role]
                may_assign_self = role in self_assignable
                name_to_role[role] = CommandRole(
                    role,
                    cmds=cmds,
                    groups=groups,
                    bases=bases,
                    assignable_roles=assignable,
                    may_assign_self=may_assign_self
                )
        self.keyword_commands_role_manager = PersistentRolesSecurityManager(self.save, name_to_role.values())

    def install(self) -> None:
        """Install this service by creating a key for it in the supplied :class:`.DataDict`."""
        self._data[self.name] = {}
        self.save()

    def installed(self) -> bool:
        """Determines whether this service is installed.

        :return: :code:`True` if :code:`self.name` is a key in the supplied :class:`.DataDict`, :code:`False` otherwise.
        """
        return self.name in self._data

    def save(self) -> None:
        """Save the state of the of the role manager to the supplied :class:`.DataDict`."""
        self._data[self.name] = {
            user: role.name
            for user, roles in self.keyword_commands_role_manager.user_to_roles.items() for role in roles
        }
        self._data.save()
