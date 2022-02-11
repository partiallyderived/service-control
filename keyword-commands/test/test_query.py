import pytest

from keywordcommands import QueryInfo


def test_checked_get() -> None:
    # Test QueryInfo._checked_get, which should raise a TypeError when the value is not of the specified type.
    assert QueryInfo._checked_get('Str', 'string', str) == 'string'
    assert QueryInfo._checked_get('Int', 3, int) == 3

    with pytest.raises(TypeError):
        QueryInfo._checked_get('Str', 3, str)

    with pytest.raises(TypeError):
        QueryInfo._checked_get('Int', '3', int)
