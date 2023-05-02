import traceback

from enough import EnumErrors

import keywordcommands.util as util


class KeywordCommandsError(Exception):
    """Base class of exceptions in this package."""


# noinspection PyUnresolvedReferences
class CommandError(KeywordCommandsError):
    """Exception class for errors that may be raised in the course of
    :meth:`handling <.CommandHandler.handle>`
    """
    @property
    def exception(self) -> str:
        return ''.join(traceback.format_exception(self.error))

    @property
    def path(self) -> str:
        return util.expand_path(self.query.path)


class CommandErrors(EnumErrors[CommandError]):
    """Exception types raised in in the course of
    :meth:`handling <.CommandHandler.handle>`.
    """
    DuplicateArgs = (
        'The following keyword arguments were specified more than once: '
            '{", ".join(duplicated)}',
        ('duplicated', 'query')
    )
    ExecutionError = 'Failed to execute command: {error}', ('error', 'query')
    MissingPath = 'No path is present in {query.text}', 'query'
    MissingRequiredArgs = (
        'The following arguments are required "{path}" but were not given: '
            '{", ".join(missing)}',
        ('missing', 'query')
    )
    NoSuchPath = '"{path}" is not a path to a group or a command.', 'query'
    NotCommand = '"{path}" is a command group, not a command.', 'query'
    ParseError = (
        'Failed to parse {arg}={value} for "{path}": {error}',
        ('arg', 'value', 'error', 'query')
    )
    UnexpectedError = (
        'An unexpected failure occurred: {exception}', ('error', 'query')
    )
    UnrecognizedArgs = (
        'The following arguments are not recognized by "{path}": '
            '{", ".join(unrecognized)}',
        ('unrecognized', 'query')
    )


class WrappedException(Exception):
    """Type of an exception which merely wraps another exception."""
    #: The wrapped exception.
    wrapped: Exception

    def __init__(self, exc_to_wrap: Exception) -> None:
        """Initialize using an exception to wrap.

        :param exc_to_wrap: Exception to wrap.
        """
        super().__init__(str(exc_to_wrap))
        self.wrapped = exc_to_wrap

    def __eq__(self, other: object) -> bool:
        """Determines whether ``self`` and ``other`` are
        :class:`WrappedExceptions <.WrappedException>` that wrap the same
        exception.

        :param other: Object to test equality against.
        :return: ``isinstance(other, WrappedException)
            and self.wrapped == other.wrapped``
        """
        return isinstance(
            other, WrappedException
        ) and self.wrapped == other.wrapped
