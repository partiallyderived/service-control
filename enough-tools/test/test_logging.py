from logging import Logger
from unittest.mock import Mock

import enough as br
from enough import SplitLevelLogger
from enough.exceptions import BRLoggingErrors


def test_split_level_logger() -> None:
    # Test SplitLevelLogger, which should delegate logging to other loggers.
    # Test that empty level_to_logger results in an error.
    with br.raises(BRLoggingErrors.EmptyMap()):
        SplitLevelLogger('empty', {})

    level_to_logger = {
        5: Mock(spec=Logger),
        10: Mock(spec=Logger),
        20: Mock(spec=Logger)
    }
    mock5: Mock = level_to_logger[5].log
    mock10: Mock = level_to_logger[10].log
    mock20: Mock = level_to_logger[20].log

    def assert_and_reset(level: int, msg: str, mock: Mock) -> None:
        # Verify that the _log function was called with the given level and message and then reset the mock.
        mock.assert_called()
        assert mock.call_args.args[:2] == (level, msg)
        mock.reset_mock()
        # Just in case, make sure the others were not called.
        for m in [mock5, mock10, mock20]:
            if m != mock:
                m.assert_not_called()

    split_logger = SplitLevelLogger('test-split-logger', level_to_logger)
    split_logger.setLevel(7)
    split_logger.log(10, 'msg')

    # Only one logger should be called.
    assert_and_reset(10, 'msg', mock10)

    # Log at a level lower than the log level and ensure no loggers were called.
    split_logger.log(5, 'msg')
    mock5.assert_not_called()
    mock10.assert_not_called()
    mock20.assert_not_called()

    # Enable all loggers.
    split_logger.setLevel(1)
    split_logger.log(5, 'msg')
    assert_and_reset(5, 'msg', mock5)

    # Try with a level below 5, which should call the logger configured with the lowest level.
    split_logger.log(3, 'msg')
    assert_and_reset(3, 'msg', mock5)

    # Between 5 and 10.
    split_logger.log(7, 'msg')
    assert_and_reset(7, 'msg', mock5)

    # Between 10 and 20.
    split_logger.log(15, 'msg')
    assert_and_reset(15, 'msg', mock10)

    # Exactly 20.
    split_logger.log(20, 'msg')
    assert_and_reset(20, 'msg', mock20)

    # Greater than 20.
    split_logger.log(100, 'msg')
    assert_and_reset(100, 'msg', mock20)
