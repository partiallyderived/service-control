from keywordcommands import Command, CommandGroup

from servicecontrol.keywordcommands.manager import (
    KeywordCommandsRoleManagerService
)

cmd1 = Command('', lambda state: state)
cmd2 = Command('', lambda state: state)
cmd3 = Command('', lambda state: state)
group1 = CommandGroup('', edge1=cmd1, edge2=cmd2)
group2 = CommandGroup('', edge3=cmd3, edge4=group1)


def test_manager() -> None:
    # Test the role manager service.
    module = test_manager.__module__

    config = {
        # Import root group from this module.
        'root': f'{module}.group2',
        'roles': {
            'role1': {
                'access': ['edge3']
            },
            'role2': {
                'access': ['edge4 edge1']
            },
            'role3': {
                'access': ['edge4']
            },
            'role4': {
                'access': ['edge3', 'edge4']
            },
            'role5': {
                'access': ['edge4 edge2'],
                'may-assign': ['role1', 'role2']
            },
            'role6': {
                # Configure self-assignable role.
                'may-assign': ['role5', 'role6']
            },
            'role7': {
                'bases': ['role2', 'role5']
            },
            'role8': {
                'access': ['edge4 edge1'],
                'bases': ['role5'],
                'may-assign': ['role2', 'role5']
            }
        }
    }
    data = {}
    # noinspection PyTypeChecker
    KeywordCommandsRoleManagerService(config, data)
