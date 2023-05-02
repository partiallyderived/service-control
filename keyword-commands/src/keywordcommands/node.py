from __future__ import annotations

import typing
from abc import abstractmethod, ABC
from collections.abc import Mapping, Sequence

import enough

if typing.TYPE_CHECKING:
    from keywordcommands import Command, CommandGroup


class _CommandNode(ABC):
    # Base class of Command and CommandGroup, which can benefit from shared
    # implementation of commands and find.
    def commands(self) -> list[tuple[list[str], Command]]:
        """Gives a sequence of tuples each containing the path to a command
        reachable from this node as its first element and the :class:`Command`
        itself as the second element.

        :return: Sequence of ``(path, command)`` for commands reachable from
            this node.
        """
        from keywordcommands.command import Command
        return [
            (path, cmd_or_group) for path, cmd_or_group in self.paths()
            if isinstance(cmd_or_group, Command)
        ]

    def find(self, path: Sequence[str]) -> Command | CommandGroup | None:
        """Find the node at the given path.

        :param path: Path to search for node with.
        :return: The found node, or ``None`` if no node could be found.
        """
        if not path:
            # For any node, always return self if the path is empty.
            # noinspection PyTypeChecker
            return self
        nxt = self.tree().get(path[0])
        if nxt:
            return nxt.find(path[1:])
        return None

    def paths(self) -> list[tuple[list[str], Command | CommandGroup]]:
        """Gets all the paths to commands and groups accessible from this node.

        :return: (path, command or group) for each command or group accessible
            from this node.
        """
        result = [([], self)]
        for edge, node in self.tree().items():
            result += [
                (enough.concat([edge], path), cmd_or_group)
                for path, cmd_or_group in node.paths()
            ]
        # noinspection PyTypeChecker
        return result

    @abstractmethod
    def tree(self) -> Mapping[str, Command | CommandGroup]:
        """Gives a tree where the strings are directed edges,
        :class:`CommandGroups <.CommandGroup>` are the non-leaf vertices, and
        :class:`Commands <.Command>` are the leaf vertices.

        :return: ``Edge -> Adjacent Vertex``
        """
        ...
