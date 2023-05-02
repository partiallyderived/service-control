from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Set
from typing import final

from enough import EnumErrors

import keywordcommands.util as util
from keywordcommands._exceptions import KeywordCommandsError
from keywordcommands.command import Command
from keywordcommands.node import _CommandNode


class GroupInitErrors(EnumErrors[KeywordCommandsError]):
    """Exception types raised in keywordcommands.group."""
    DuplicateEdges = (
        'Could not initialize CommandGroup because the following edges have '
            'the same case-insensitive name as another edge: '
            '{", ".join(duplicated)}',
        'duplicated'
    )
    MalformedEdges = (
        'Could not initialize CommandGroup because the following edges contain '
            'characters which are not letters, digits, or hyphens: '
            '{", ".join(malformed)}',
        'malformed'
    )


@final
class CommandGroup(_CommandNode):
    """Represents a group of commands and allows for selecting and executing the
    commands from a string of arguments.
    """

    # Tree linking paths to other nodes.
    _tree: OrderedDict[str, Command | CommandGroup]

    #: Description of this command group.
    description: str

    @staticmethod
    def _check_for_dupes(kwargs: Mapping[str, Command | CommandGroup]) -> None:
        # Checks __init__ kwargs to see if any keys are the same when case is
        # ignored.
        duplicated = set()
        seen = set()
        for k, v in kwargs.items():
            lower = k.lower()
            if lower in seen:
                duplicated.add(lower)
            seen.add(lower)
        if duplicated:
            raise GroupInitErrors.DuplicateEdges(duplicated=duplicated)

    @staticmethod
    def _check_malformed_edges(edges: Set[str]) -> None:
        # Finds any malformed edge strings and raises an exception if there are
        # any.
        malformed = {e for e in edges if not util.VALID_WORD.fullmatch(e)}
        if malformed:
            raise GroupInitErrors.MalformedEdges(malformed=malformed)

    def __init__(
        self, description: str, /, **kwargs: Command | CommandGroup
    ) -> None:
        """Initializes this group using the given mapping from edge strings to
        :class:`CommandNodes <.CommandNode>`.

        :param description: Description of this command group.
        :param kwargs: Mapping from edge strings to other
            :class:`CommandNodes <.CommandNode>`.
        :raise CommandGroupInitError: If any keys in ``kwargs`` are the same
            when case is ignored or contain characters which are not letters,
            digits, or hyphens.
        """
        self.description = description
        self._check_malformed_edges(kwargs.keys())
        self._check_for_dupes(kwargs)
        # Commands in alphabetical order.
        self._tree = OrderedDict(sorted(
            [(k.lower(), v) for k, v in kwargs.items()], key=lambda x: x[0]
        ))

    def tree(self) -> OrderedDict[str, 'Command | CommandGroup']:
        """Gives a graph where the strings are directed edges and
        :class:`CommandNodes <.CommandNode>` are the vertices for which there is
        a directed edge from ``self`` to the other vertices.

        :return: ``Edge -> Adjacent Vertex``
        """
        return self._tree
