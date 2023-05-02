from collections import OrderedDict

import keywordcommands.util as util


def test_expand_args() -> None:
    # Test expand_args, which should take a sequence of strings and a mapping
    # from str to str and expand them to the corresponding user string which
    # corresponds to that path and those keyword arguments.
    assert util.expand_args([], {}) == ' '
    assert util.expand_args(['one'], {}) == 'one '
    # Next line removed because it is unclear whether a space should precede the
    # resulting k=v pairs if the path is
    # empty. It's not a real use case anyway.
    # assert util.expand_args([], {'key1': 'val1'}) == 'key1=val1'
    assert util.expand_args(['one'], {'key1': 'val1'}) == 'one key1=val1'

    # Need OrderedDict or else this isn't necessarily true.
    assert util.expand_args(
        ['one', 'two', 'three'],
        OrderedDict([('key1', 'val1'), ('key2', 'val2'), ('key3', 'val3')])
    ) == 'one two three key1=val1 key2=val2 key3=val3'


def test_expand_kwargs() -> None:
    # Test expand_kwargs, which should take a mapping from str to str and create
    # a space-separated string of key=value.
    assert util.expand_kwargs({}) == ''
    assert util.expand_kwargs({'key1': 'val1'}) == 'key1=val1'

    # Need OrderedDict or else this isn't necessarily true.
    assert util.expand_kwargs(OrderedDict(
        [('key1', 'val1'), ('key2', 'val2'), ('key3', 'val3')]
    )) == 'key1=val1 key2=val2 key3=val3'


def test_expand_path() -> None:
    # Test expand_path, which should convert a sequence of strings into a single
    # space-separated string.
    assert util.expand_path([]) == ''
    assert util.expand_path(['one']) == 'one'
    assert util.expand_path(['one', 'two', 'three', 'four']) == (
        'one two three four'
    )


def test_num_required_pos_args() -> None:
    # Test num_required_pos_args, which should count the number of required
    # positional arguments.
    assert util.num_required_pos_args(lambda: None) == 0
    assert util.num_required_pos_args(lambda x, y: None) == 2
    assert util.num_required_pos_args(lambda x=1, y=2: None) == 0
    assert util.num_required_pos_args(lambda a, b, c=1, d=2, e=3: None) == 2

    # noinspection PyUnusedLocal
    def has_kwonly(a: int, b: int, c: int = 3, *, d: int, e: int = 4): pass
    assert util.num_required_pos_args(has_kwonly) == 2

    # Make sure it counts self only when appropriate.
    class Class:
        def method1(self, a: int, b: int) -> None: pass
        def method2(self, a: int, b: int, c: int = 3) -> None: pass

    assert util.num_required_pos_args(Class.method1) == 3
    assert util.num_required_pos_args(Class.method2) == 3

    instance = Class()
    assert util.num_required_pos_args(instance.method1) == 2
    assert util.num_required_pos_args(instance.method2) == 2


def test_uncapitalize() -> None:
    # Test uncapitalize, should make the first letter of a string lowercase if
    # it's capitalized.
    assert util.uncapitalize('word') == 'word'
    assert util.uncapitalize('Word') == 'word'
    assert util.uncapitalize('wORD') == 'wORD'
    assert util.uncapitalize('WORD') == 'wORD'
