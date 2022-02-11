import re
from abc import ABC, abstractmethod
from re import Pattern
from typing import final, Final

import keywordcommands.util as util
from keywordcommands._exceptions import CommandError, CommandErrors
from keywordcommands.command import Command
from keywordcommands.group import CommandGroup
from keywordcommands.query import QueryResult
from keywordcommands.security import SecurityError
from keywordcommands.state import CommandState, DefaultCommandState


class CommandHandler(ABC):
    """Handles the execution of keyword commands."""

    # Regex to find escaped equals.
    _ESCAPED_EQUALS_REGEX: Final[Pattern] = re.compile(fr'({util.VALID_WORD.pattern}\\*)\\=')

    # Regex to find keywords.
    _KEYWORD_REGEX: Final[Pattern] = re.compile(fr'({util.VALID_WORD.pattern})=')

    @staticmethod
    def _unescaped(string: str) -> str:
        # Returns the given string where instances where we would find a keyword argument if it were not for the
        # presence of a one or more backslashes preceding the equals sign are replaced with one less backslash. Used
        # when something like "this=true" is meant to be used in a value, in which case the substitution "this\=true"
        # will suffice, or, if a *that* is the desired literal string, "this\\=true" will suffice, and so on.
        return CommandHandler._ESCAPED_EQUALS_REGEX.sub(r'\1=', string)

    @staticmethod
    def parse(text: str) -> tuple[list[str], dict[str, str], set[str]]:
        """Parse the given command text into a parsed path sequence and parsed keyword arguments. Errors such as
        paths or arguments with malformed characters or duplicated arguments do not result in an exception: instead,
        the parsed result is returned and the caller decides how to deal with the exceptional, all of which may be
        inferred from the returned values.

        :param text: Text to parse.
        :return: (path, keyword arguments, duplicated arguments)
        """
        kw_matches = list(CommandHandler._KEYWORD_REGEX.finditer(text))
        if kw_matches:
            # Command args end before the first match.
            path_str = text[:kw_matches[0].start()].strip()
        else:
            # The entire string is the path.
            path_str = text

        # Parse the command path from the given string.
        # Split on whitespace. While commands may only have letters, numbers, or hyphens, it is sufficient to fail with
        # NoSuchPathException later.
        # Force lowercase for path.
        path = [e.lower() for e in path_str.split()]
        kwargs = {}
        duplicated = set()
        for i, m in enumerate(kw_matches):
            kw = m.group(1).lower()
            if kw in kwargs:
                duplicated.add(kw)
            # The value is located from the character after the equals sign to the start of the next match or the end of
            # the string if this is the last match, with whitespace stripped.
            value_start = m.end()
            if i == len(kw_matches) - 1:
                # Last match, use the end of the string.
                value_end = len(text)
            else:
                # Not the last match, use the start of the next match
                value_end = kw_matches[i + 1].start()
            value = text[value_start:value_end].strip()
            # Remove escape characters if necessary.
            kwargs[kw] = CommandHandler._unescaped(value)
        return path, kwargs, duplicated

    @abstractmethod
    def handle_cmd_help(self, state: CommandState) -> None:
        """Handle request for help for a command.

        :param state: State to use or modify.
        """
        ...

    @abstractmethod
    def handle_error(self, state: CommandState) -> None:
        """Handle the situation in which an exception was raised in the course of running
        :meth:`.CommandHandler.handle`.

        :param state: State to use or modify.
        """
        ...

    @abstractmethod
    def handle_general_help(self, state: CommandState) -> None:
        """Handle top-level request for help.

        :param state: State to use or modify.
        """
        ...

    @abstractmethod
    def handle_group_help(self, state: CommandState) -> None:
        """Handle request for help for a command group.

        :param state: State to use or modify.
        """
        ...

    @abstractmethod
    def handle_help_not_found(self, state: CommandState) -> None:
        """Handle situation where help is requested for a command that could not be found.

        :param state: State to use or modify.
        """
        ...

    @abstractmethod
    def handle_success(self, state: CommandState) -> None:
        """Handle top-level request for help.

        :param state: State to use or modify.
        """
        ...

    @abstractmethod
    def pre_execute(self, state: CommandState) -> None:
        """This method is run after all parsing is complete but before the command is executed.

        :param state: State to use or modify.
        """
        ...

    @final
    def handle(self, state: CommandState, text: str) -> None:
        """Handle the command text entered by the user. Should not be overridden by subclasses: override the other
        handle methods and :meth:`.CommandHandler.pre_execute` instead.

        :param state: State for other instance methods to use or modify.
        :param text: The user command text to handle.
        """
        query = state.query
        query.text = text
        try:
            path, kwargs, duplicated = self.parse(text)
            is_help = not (path or kwargs) or path[0] == 'help'
            if is_help:
                path = path[1:]
            query.path = path
            query.kwargs = kwargs
            query.is_help = is_help
            query.node = query.root.find(path)
            if duplicated and not is_help:
                raise CommandErrors.DuplicateArgs(duplicated=duplicated, query=query)
            match query.node, is_help:
                case query.root, True:
                    query.result = QueryResult.GENERAL_HELP
                    self.handle_general_help(state)
                case query.root, False:
                    # (query.root, False) means we have an empty path, but were given keyword arguments.
                    # In this case, raise an exception instead of defaulting to help.
                    assert kwargs
                    raise CommandErrors.MissingPath(query=query)
                case Command(), False:
                    query.parsed = query.cmd.parse(state, kwargs)
                    self.pre_execute(state)
                    query.cmd(state, query.parsed)
                    query.result = QueryResult.SUCCESS
                    self.handle_success(state)
                case Command(), True:
                    query.result = QueryResult.CMD_HELP
                    self.handle_cmd_help(state)
                case CommandGroup(), False:
                    raise CommandErrors.NotCommand(query=query)
                case CommandGroup(), True:
                    query.result = QueryResult.GROUP_HELP
                    self.handle_group_help(state)
                case None, False:
                    raise CommandErrors.NoSuchPath(query=query)
                case None, True:
                    query.result = QueryResult.HELP_NOT_FOUND
                    self.handle_help_not_found(state)
                case _:
                    raise AssertionError('Should not be reachable.')
        except Exception as e:
            query.error = e
            if not isinstance(e, CommandError):
                query.error = CommandErrors.UnexpectedError(error=e, query=query)
            query.result = type(query.error)
            self.handle_error(state)


class DefaultCommandHandler(CommandHandler):
    """Default implementation of :class:`.CommandHandler` which uses a :class:`.DefaultCommandState` to check if the
    execution of a command does not violate security configurations and also to format and send user messages.
    """

    @staticmethod
    def send_query_msg(state: DefaultCommandState) -> None:
        """Use the given state's :class:`.QueryFormatter` to format a message to send based on the values set on
        :code:`state.query`.

        :param state: State to format and send message with.
        """
        DefaultCommandHandler.send_user_msg(state, state.formatter.user_msg(state.query))

    @staticmethod
    def send_user_msg(state: DefaultCommandState, msg: str | None) -> None:
        """Send a message to the calling user using the given state's messenger.

        :param state: State to send message with.
        :param msg: The message to send.
        """
        if msg is not None:
            state.messenger(msg)

    def handle_cmd_help(self, state: DefaultCommandState) -> None:
        """Handle a request for help for a command by sending a message using the state's formatter and messenger.

        :param state: State to handle command help with.
        """
        self.send_query_msg(state)

    def handle_error(self, state: DefaultCommandState) -> None:
        """Handle the situation in which an error is raised by sending a message using the state's formatter and
        messenger.

        :param state: State to handle with.
        """
        self.send_query_msg(state)

    def handle_general_help(self, state: DefaultCommandState) -> None:
        """Handle a request for top-level application help by sending a message using the state's formatter and
        messenger.

        :param state: State to handle command help with.
        """
        self.send_query_msg(state)

    def handle_group_help(self, state: DefaultCommandState) -> None:
        """Handle a request for help for a command group by sending a message using the state's formatter and messenger.

        :param state: State to handle command help with.
        """
        self.send_query_msg(state)

    def handle_help_not_found(self, state: DefaultCommandState) -> None:
        """Handle the situation in which a user has requested help for a command that could not be found using the
        state's formatter and messenger.

        :param state: State to handle with.
        """
        self.send_query_msg(state)

    def handle_success(self, state: DefaultCommandState) -> None:
        """Handle the case where a command is executed successfully.

        :param state: State to handle success with.
        """
        self.send_query_msg(state)

    def pre_execute(self, state: DefaultCommandState) -> None:
        """Use the given state's :class:.`SecurityManager` to raise an exception if the command should not be executed.

        :param state: State whose security manager will be used.
        :raise CommandError: If there is insufficient access to execute using the given state.
        """
        with CommandErrors.ExecutionError.wrap_error(SecurityError, query=state.query):
            # Treat this error as though it were an execution error (for now).
            state.security_manager.raise_if_cannot_execute(state)
