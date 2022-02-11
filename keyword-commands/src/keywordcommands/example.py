from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import keywordcommands.util as util


@dataclass
class Example:
    """Represents example usage."""

    #: Description of what the example does.
    description: str

    #: The keyword arguments the example uses. Use an :code:`OrderedDict` to ensure argument order if desired for help
    # messages.
    kwargs: Mapping[str, str]

    #: Determines whether an attempt to parse this argument should be made. When unchecked is :code:`False`
    #: (the default), a :class:`.Command` will attempt to parse with the example args upon creation and raise an
    #: :code:`AssertionError` on failure. Otherwise, no check will be performed, which may be useful if for example the
    #: parser relies on a service which has not yet been created or started.
    unchecked: bool = False

    def expand(self, path: Sequence[str]) -> str:
        """Expands this example into a string which represents the command arguments that comprise this example.

        :param path: The path to expand with.
        :return: The expanded example.
        """
        return util.expand_args(path, self.kwargs)
