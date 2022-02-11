import os
from threading import Thread

import pytest

import enough as br
from enough.exceptions import BRFuncErrors


def test_bounds() -> None:
    # Test bounds, which should get the lower and upper bounds of a given value in the given collection.
    assert br.bounds(3, []) == (None, None)
    assert br.bounds(3, [4]) == (None, 4)
    assert br.bounds(3, [2]) == (2, None)
    assert br.bounds(3, [3]) == (3, 3)
    assert br.bounds(3, [2, 4]) == (2, 4)
    assert br.bounds(3, [7, 4]) == (None, 4)
    assert br.bounds(3, [0, 0, -1, 1, 1, 2, 0, -2]) == (2, None)
    assert br.bounds(3, [7, 8, 6, 9, 4, 5, 5, 10]) == (None, 4)
    assert br.bounds(3, [0, 2, 10, 4, 5, 1, -4]) == (2, 4)
    assert br.bounds(3, [0, 2, 10, 4, 3, 5, 1, -4]) == (3, 3)


def test_concat() -> None:
    # Test concat, which should concatenate two sequences into a list.
    assert br.concat([], []) == []
    assert br.concat(['ab', 'cd'], []) == ['ab', 'cd']
    assert br.concat([], ['ef', 'gh']) == ['ef', 'gh']
    assert br.concat(['ab', 'cd'], ['ef', 'gh']) == ['ab', 'cd', 'ef', 'gh']


def test_dag_stages() -> None:
    # Test that dag_stages correctly determines a series of stages given a dependency map.

    # In the following dependency map, 1, 3, and 5 should be in stage 0, while 2, 4 should be in stage 1, and 6 should
    # be in stage 2. Note that 3 and 5 are inferred to be in stage 0 while 1 is explicit.
    assert br.dag_stages({
        1: [],
        2: [3, 5],
        4: [1, 5],
        6: [2]
    }) == [{1, 3, 5}, {2, 4}, {6}]

    # Check that disconnected graphs don't cause an issue.
    assert br.dag_stages({2: [1], 3: {4}}) == [{1, 4}, {2, 3}]

    # Check that a circular dependency is correctly detected.
    # noinspection PyTypeChecker
    with pytest.raises(BRFuncErrors.CircularDependency) as exc_info:
        br.dag_stages({
            1: [2],
            2: [3],
            3: [4],
            4: [1]
        })
    # 4 possible paths for this execution order.
    assert exc_info.value.path in [
        [1, 2, 3, 4, 1],
        [2, 3, 4, 1, 2],
        [3, 4, 1, 2, 3],
        [4, 1, 2, 3, 4]
    ]


def test_flatten() -> None:
    # Test that bobbeyreese.flatten reduces the dimension of a collection by one.
    assert br.flatten([]) == []
    assert br.flatten([[1, 2]]) == [1, 2]
    assert br.flatten([[1], [2, 3], [4, 5, 6]]) == [1, 2, 3, 4, 5, 6]


def test_format_fields() -> None:
    # Test that bobbeyreese.format_fields(str) gives all format fields in that string.
    assert br.format_fields('a b c d') == set()
    assert br.format_fields('{a} b {c} d') == {'a', 'c'}
    assert br.format_fields('{apple} {banana} {coconut}') == {'apple', 'banana', 'coconut'}


def test_format_table() -> None:
    # Test that bobbeyreese.format_table gives a string representation of a table.
    table = [('Row 1', [
        1, 2, 3
    ]), ('Row 2', [
        4, 5
    ]), ('Row 3', [
        6, 7, 8, 9
    ])]
    assert br.format_table(table) == (
        'Row 1: 1, 2, 3\n'
        'Row 2: 4, 5\n'
        'Row 3: 6, 7, 8, 9'
    )
    assert br.format_table(table, row_sep='\t') == 'Row 1: 1, 2, 3\tRow 2: 4, 5\tRow 3: 6, 7, 8, 9'
    assert br.format_table(table, col_sep='  ') == (
        'Row 1: 1  2  3\n'
        'Row 2: 4  5\n'
        'Row 3: 6  7  8  9'
    )
    assert br.format_table(table, key_sep=' -> ') == (
        'Row 1 -> 1, 2, 3\n'
        'Row 2 -> 4, 5\n'
        'Row 3 -> 6, 7, 8, 9'
    )
    assert br.format_table(table, key_fn=lambda x: x.upper()) == (
        'ROW 1: 1, 2, 3\n'
        'ROW 2: 4, 5\n'
        'ROW 3: 6, 7, 8, 9'
    )
    assert br.format_table(table, val_fn=float) == (
        'Row 1: 1.0, 2.0, 3.0\n'
        'Row 2: 4.0, 5.0\n'
        'Row 3: 6.0, 7.0, 8.0, 9.0'
    )


def test_fqln() -> None:
    # Test that bobbeyreese.fqln(cls) gives the fully-qualified class name for cls.
    assert br.fqln(Thread) == 'threading.Thread'


def test_raises() -> None:
    # Test that raises can check exception instance equality.
    # Exceptions are not equal even if all their data is equal.
    with pytest.raises(AssertionError):
        with br.raises(Exception('asdf')):
            raise Exception('asdf')

    class ComparableError(Exception):
        def __init__(self, a: int) -> None:
            self.a = a

        def __eq__(self, other: object) -> bool:
            return isinstance(other, ComparableError) and self.a == other.a

    with br.raises(ComparableError(5)):
        raise ComparableError(5)

    with pytest.raises(AssertionError):
        with br.raises(ComparableError(5)):
            raise ComparableError(4)


def test_temp_file_path() -> None:
    # Test that temp_file_path can be used to create a temporary file and return the string path, deleting the file
    # after it exits if delete was specified to be True (the default).
    with br.temp_file_path() as path:
        assert os.path.isfile(path)
    assert not os.path.isfile(path)

    # Ensure that the file still exists after the context manager exits if delete is False.
    with br.temp_file_path(delete=False) as path:
        assert os.path.isfile(path)
    assert os.path.isfile(path)
    os.remove(path)

    # Ensure that deleting the file before the context manager exits when delete=True does not result in an error.
    with br.temp_file_path() as path:
        os.remove(path)
