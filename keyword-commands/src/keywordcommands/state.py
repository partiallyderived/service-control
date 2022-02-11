from abc import abstractmethod, ABC
from collections.abc import Callable
from typing import Generic

from enough import T

from keywordcommands.format import DefaultQueryFormatter, QueryFormatter
from keywordcommands.group import CommandGroup
from keywordcommands.query import QueryInfo
from keywordcommands.security import SecurityManager


class CommandState:
    """Represents a state with objects needed for command handling and execution."""

    #: :class:`.QueryInfo` instance describing the user's input.
    query: QueryInfo

    def __init__(self, name: str, root: CommandGroup) -> None:
        """Initialize this state.

        :param name: Application name to initialize with.
        :param root: Root :class:`.CommandGroup` to initialize with.
        """
        self.query = QueryInfo(name, root)

    def reset(self) -> None:
        """Call this to restore :code:`self` to its initial state."""
        self.query = QueryInfo(self.query.name, self.query.root)


class DefaultCommandState(CommandState):
    """:class:`.CommandState` containing state information needed by :class:`.DefaultCommandHandler`."""
    #: Formatter to use to format :class:`.QueryInfo` instances.
    formatter: QueryFormatter

    #: Function to use to send user messages.
    messenger: Callable[[str], object]

    #: :class:`.SecurityManager` to use.
    security_manager: SecurityManager

    def __init__(
        self,
        name: str,
        root: CommandGroup,
        *,
        formatter: QueryFormatter | None = None,
        messenger: Callable[[str], object] = print,
        security_manager: SecurityManager | None = None
    ) -> None:
        """Initializes this from the given top-level application data.

        :param name: Name of the top-level application.
        :param root: Root :class:`.CommandGroup` from which all commands originate.
        :param formatter: Formatter to use to format query messages.
        :param messenger: Callable to use to send user messages.
        :param security_manager: Security manager to use to check when an action may be performed. If unspecified, all
            actions are permitted.
        """
        super().__init__(name, root)
        self.formatter = formatter or DefaultQueryFormatter()
        self.messenger = messenger
        self.security_manager = security_manager or SecurityManager()


class UserState(ABC, DefaultCommandState, Generic[T]):
    """Represents a state which can determine the executing user."""

    @property
    @abstractmethod
    def user(self) -> T:
        ...
