import inspect

import enough as br

import keywordcommands.util as util
from keywordcommands import CommandState, Parser, parser
from keywordcommands.exceptions import ParserInitErrors


def test_ensure_state_arg() -> None:
    # Test Parser.ensure_state_arg, which should convert functions with one argument to functions with two arguments
    # and leave functions with two arguments untouched.

    def one_arg(arg: str) -> str: return arg

    # noinspection PyUnusedLocal
    def two_args(arg: str, state: CommandState | None) -> str: return arg

    assert len(inspect.getfullargspec(Parser.ensure_state_arg(one_arg)).args) == 2
    assert Parser.ensure_state_arg(two_args) == two_args

    def no_args() -> None: return None
    with br.raises(ParserInitErrors.BadNumArgs(fn=no_args)):
        Parser.ensure_state_arg(no_args)

    # noinspection PyUnusedLocal
    def three_args(arg1: str, arg2: str, arg3: str) -> str: return arg1
    with br.raises(ParserInitErrors.BadNumArgs(fn=three_args)):
        Parser.ensure_state_arg(three_args)

    # Do the same tests, but with bound methods.
    # noinspection PyMethodMayBeStatic
    class Parsers:
        def no_args(self) -> None: return None
        def one_arg(self, arg: str) -> str: return arg

        # noinspection PyUnusedLocal
        def two_args(self, arg: str, state: CommandState | None) -> str: return arg

        # noinspection PyUnusedLocal
        def three_args(self, arg1: str, arg2: str, arg3: str) -> str: return arg1

    instance = Parsers()

    with br.raises(ParserInitErrors.BadNumArgs(fn=instance.no_args)):
        Parser.ensure_state_arg(instance.no_args)

    one_arg_fn = Parser.ensure_state_arg(instance.one_arg)
    assert one_arg_fn != instance.one_arg
    assert not inspect.ismethod(one_arg_fn)
    assert len(inspect.getfullargspec(one_arg_fn).args) == 2

    assert Parser.ensure_state_arg(instance.two_args) == instance.two_args

    with br.raises(ParserInitErrors.BadNumArgs(fn=instance.three_args)):
        Parser.ensure_state_arg(instance.three_args)

    # Case with keyword arguments and defaults which is fine.
    # noinspection PyUnusedLocal
    def good_kw1(arg1: str, state: CommandState | None, arg2: str = 'asdf', *, arg3: str = 'fdsa') -> str: return arg1
    assert Parser.ensure_state_arg(good_kw1) == good_kw1

    # Another case which is fine. Should result in new function.
    # noinspection PyUnusedLocal
    def good_kw2(arg1: str, arg2: str = 'asdf', *, arg3: str = 'fdsa') -> str: return arg1
    assert util.num_required_pos_args(Parser.ensure_state_arg(good_kw2)) == 2

    # Case with a keyword argument without a default, which is not allowed.
    # noinspection PyUnusedLocal
    def bad_kw(arg1: str, state: CommandState | None, *, arg2: str) -> str: return arg1

    with br.raises(ParserInitErrors.BadKWArgs(fn=bad_kw)):
        Parser.ensure_state_arg(bad_kw)


def test_decorator() -> None:
    # Test the parser decorator, which should convert a function of a single argument into a Parser instance.
    @parser('an integer')
    def to_int(arg: str) -> int:
        return int(arg)

    assert type(to_int) == Parser
    assert to_int('3', None) == 3
    assert to_int.expected_format == 'an integer'

    # noinspection PyUnusedLocal
    @parser('a float')
    def to_float(arg: str, state: CommandState) -> float:
        return float(arg)

    assert to_float('3.14', None) == 3.14
