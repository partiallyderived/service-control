from __future__ import annotations

import unittest.mock as mock
from dataclasses import dataclass
from typing import ClassVar

import pytest

from bobbeyreese import ChainedFmtError, FmtError, ImportFmtError, MultiFmtError
from bobbeyreese.exceptions import MissingCauseError


def test_fmt_error() -> None:
    # Test the FmtError class, wherein an exception method can be specified by implementing _fmt.

    @dataclass
    class FmtErrorChild(FmtError):
        _fmt: ClassVar[str] = '{a} {"=" if a == b else "!="} {b} (btw, {c})'
        # Note the lack of a definition for _fmt.
        a: int
        b: int

        def _vars(self) -> dict[str, object]:
            return {**super()._vars(), 'c': "you're cool"}

    assert str(FmtErrorChild(1, 1)) == "1 = 1 (btw, you're cool)"
    assert str(FmtErrorChild(1, 2)) == "1 != 2 (btw, you're cool)"

    # Test that a subclass can use the "args" attribute.
    @dataclass
    class ArgsFmtError(FmtError):
        args: list[int]
        _fmt: ClassVar[str] = 'args: {", ".join(str(a) for a in args)}'

    assert str(ArgsFmtError([1, 2, 3])) == 'args: 1, 2, 3'


def test_chained_fmt_error() -> None:
    # Test ChainedFmtError, which should call _error_msg to generate an exception method from the given error.
    class TestChainedError(ChainedFmtError[ValueError]):
        _fmt: ClassVar[str] = 'Got an error:\n{error}'

    with mock.patch('traceback.format_exception') as mock_fmt_exc:
        mock_fmt_exc.return_value = ['m', 's', 'g']
        with pytest.raises(MissingCauseError):
            # Default construction should result in MissingCauseError being raised unless we are handling an exception.
            TestChainedError()
        mock_fmt_exc.assert_not_called()

        # Now try in an except block.
        try:
            raise ValueError('asdf')
        except Exception as e:
            chained = TestChainedError()
            assert chained.error == e
            assert str(chained) == (
                'Got an error:\n'
                'msg'
            )
            mock_fmt_exc.assert_called_with(e)
            mock_fmt_exc.reset_mock()

        # Specify the error explicitly.
        error = ValueError('fdsa')
        chained = TestChainedError(error)
        assert chained.error == error
        str(chained)
        mock_fmt_exc.assert_called_with(chained.error)
        mock_fmt_exc.reset_mock()


def test_import_fmt_error() -> None:
    # Test that FmtErrors subclasses with ImportError can use the path and name attributes.
    @dataclass
    class ImportFmtErrorChild(ImportFmtError):
        _fmt: ClassVar[str] = '{path}: {name}'
        name: str
        path: str

    e = ImportFmtErrorChild(name='Class', path='a/b/c.py')
    assert str(e) == 'a/b/c.py: Class'
    assert e.msg == str(e)


def test_multi_fmt_error() -> None:
    # Test MultiFmtError, which allows for the formatting of multiple errors.
    # Make an implementing subclass.
    class TestMultiError(MultiFmtError[Exception]):
        _fmt: ClassVar[str] = 'errors:\n\n{errors}'

    # Make the errors and a traceback object.
    error1 = ValueError('asdf')
    error2 = KeyError('fdsa')
    error3 = Exception('3.14')

    with mock.patch('traceback.format_exception') as mock_fmt_exc:
        mock_fmt_exc.return_value = ['m', 's', 'g']

        # Need this to explicitly be a string so that join doesn't raise.
        multi_error = TestMultiError([error1, error2, error3])
        assert str(multi_error) == (
            'errors:\n\n'
            ''
            'msg\n\n'
            ''
            'msg\n\n'
            ''
            'msg'
        )
        mock_fmt_exc.assert_has_calls([
            mock.call(error1),
            mock.call(error2),
            mock.call(error3)
        ])
