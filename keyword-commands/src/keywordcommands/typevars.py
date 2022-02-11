import typing
from typing import TypeVar

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from keywordcommands import CommandState

# For the type of a state.
S = TypeVar('S', bound='CommandState', contravariant=True)
