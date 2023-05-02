import logging
from collections.abc import Callable, Mapping
from logging import Handler, LogRecord, Logger, LoggerAdapter
from typing import Any

import enough
from enough._exception import EnoughError
from enough.enumerrors import EnumErrors


class EnoughLoggingErrors(EnumErrors[EnoughError]):
    """Exception types raised in enough.logging."""
    EmptyMap = 'level_to_logger may not be empty.', (), ValueError


class FnLoggingHandler(Handler):
    """Logger handler which logs messages using a function accepting a
    string.
    """

    #: The function to log messages with.
    fn: Callable[[str], object]

    def __init__(
        self, fn: Callable[[str], object], level: int = logging.NOTSET
    ) -> None:
        """Initialize this handler with the given function.

        :param fn: Function to call to log the message.
        :param level: Logging level to use.
        """
        super().__init__(level)
        self.fn = fn

    def emit(self, record: LogRecord) -> None:
        """Emit a log statement by calling the configured function with the
        formatted record.

        :param record: Record to format.
        """
        self.fn(self.format(record))


class SplitLevelLogger(LoggerAdapter):
    """Logger subclass which delegates logging to multiple other loggers based
    on the level of the message. Assumes that the number of unique levels logged
    with does not grow without bound, otherwise this is a very inefficient
    implementation.
    """

    #: Mapping from level to logger to use. Updated as logs are attempted with
    #: more levels.
    level_to_logger: dict[int, Logger]

    def __init__(
        self, name: str, level_to_logger: Mapping[int, Logger | LoggerAdapter]
    ) -> None:
        """Initializes this logger.

        :param name: Name to give to this logger.
        :param level_to_logger: Mapping from logging levels to loggers to be
            used. The actual log levels of these loggers is ignored and set to
            1.
        :raise EnoughError: If ``level_to_logger`` is empty.
        """
        if not level_to_logger:
            raise EnoughLoggingErrors.EmptyMap()
        super().__init__(logging.getLogger(name), None)
        self.level_to_logger = dict(level_to_logger)
        # Ignore levels set in given loggers.
        [logger.setLevel(1) for logger in level_to_logger.values()]

    def log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        # Overwrite this log function to delegate to other loggers.
        if self.isEnabledFor(level):
            logger = self.level_to_logger.get(level)
            if not logger:
                # Find the logger corresponding to the greatest lower bound for
                # level in level_to_logger.
                glb = enough.bounds(level, self.level_to_logger)[0]
                if glb is None:
                    # This level is lower than any other configured level. In
                    # this case, use the lowest level.
                    logger = self.level_to_logger[min(self.level_to_logger)]
                else:
                    logger = self.level_to_logger[glb]
                # Update the level mapping so we don't have to do this
                # calculation again.
                self.level_to_logger[level] = logger
            logger.log(level, msg, *args, **kwargs)
