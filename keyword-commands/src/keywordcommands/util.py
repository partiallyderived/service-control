import inspect
import re
from collections.abc import Callable, Mapping, Sequence
from re import Pattern
from typing import Final


#: Regex of valid commands or keywords.
VALID_WORD: Final[Pattern] = re.compile(r'[a-zA-Z0-9-]+')


def expand_args(path: Sequence[str], kwargs: Mapping[str, str]) -> str:
    """Expands the given parsed command arguments by joining the expanded path and keyword arguments.

    :param path: The path to expand.
    :param kwargs: The keyword arguments to expand.
    :return: The expanded string.
    """
    return f'{expand_path(path)} {expand_kwargs(kwargs)}'


def expand_kwargs(kwargs: Mapping[str, object]) -> str:
    """Expands the given keyword arguments into a space-separated string of <key>=<value>.

    :param kwargs: Keyword arguments to expand.
    :return: The expanded string.
    """
    return ' '.join(f'{k}={v}' for k, v in kwargs.items())


def expand_path(path: Sequence[str]) -> str:
    """Expands the given path into a space-separated string of <edge 1>, <edge 2>, ...

    :param path: The path to expand.
    :return: The expanded path.
    """
    return ' '.join(path)


def num_required_pos_args(fn: Callable) -> int:
    """Get the number of required positional arguments for the given function.

    :param fn: Function to count required positional arguments for.
    :return:
    """
    spec = inspect.getfullargspec(fn)
    # Total pos args - defaults - self if it's a bound method.
    return len(spec.args) - len(spec.defaults or ()) - bool(inspect.ismethod(fn))


def uncapitalize(string: str) -> str:
    """"Uncapitalize" a string by concatenating the lower-cased first character with the remaining of the string.

    :param string: String to "uncapitalize".
    :return: The uncapitalized string.
    """
    return string[0].lower() + string[1:]
