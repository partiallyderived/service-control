from collections.abc import Mapping, Sequence
from enum import Enum, auto

import enough as br
from enough import T

from keywordcommands._exceptions import CommandError, KeywordCommandsError
from keywordcommands.command import Command
from keywordcommands.group import CommandGroup


class QueryResult(Enum):
    """Enumeration of possible non-error results of the query. Error results are enumerated in
    :class:`.ProcessErrorContext`.
    """
    SUCCESS = auto()
    GENERAL_HELP = auto()
    GROUP_HELP = auto()
    CMD_HELP = auto()
    HELP_NOT_FOUND = auto()


class QueryInfo:
    """Contains information about a processed user query."""

    #: The resulting exception, if applicable.
    error: CommandError | None = None

    #: :code:`True` if the query is a help query, :code:`False` otherwise.
    is_help: bool | None = None

    #: The unparsed keyword arguments entered by the user, if applicable.
    kwargs: Mapping[str, str] | None = None

    #: Name of the top-level application.
    name: str

    #: :class:`.Command` or :class`.CommandGroup` the user entered, if applicable.
    node: Command | CommandGroup | None = None

    #: The parsed keyword arguments entered by the user, if applicable.
    parsed: Mapping[str, object] | None = None

    #: Path the user entered, if applicable.
    path: Sequence[str] | None = None

    #: Result of the query, if complete.
    result: QueryResult | KeywordCommandsError | None = None

    #: The root command group.
    root: CommandGroup

    #: Raw string passed to :meth:`.CommandHandler.parse`.
    text: str | None = None

    @staticmethod
    def _checked_get(name: str, value: object, typ: type[T]) -> T:
        if not isinstance(value, typ):
            raise TypeError(f'{name} is not an instance of {br.fqln(typ)}')
        return value

    def __init__(self, name: str, root: CommandGroup) -> None:
        """Initialize this query with the given top-level information.

        :param name: Name of the top-level application.
        :param root: The root command group.
        """
        self.name = name
        self.root = root

    @property
    def cmd(self) -> Command:
        """The command the user entered.

        :return: The command the user entered.
        :raise TypeError: If no command was parsed for this query.
        """
        return self._checked_get('Node', self.node, Command)

    @property
    def group(self) -> CommandGroup:
        """The command group the user entered.

        :return: The command group the user entered.
        :raise TypeError: If no command group was parsed for this query.
        """
        return self._checked_get('Node', self.node, CommandGroup)
