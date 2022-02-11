from typing import Generic

from enough import EnumErrors, V

import keywordcommands.util as util
from keywordcommands._exceptions import KeywordCommandsError
from keywordcommands.parser import Parser


class ArgInitContext(EnumErrors[KeywordCommandsError]):
    """Exception types raised in keywordcommands.arg."""
    MalformedName = (
        'Cannot create Arg with name {name}: argument names may not contain characters which are not numbers, letters '
            'or hyphens',
        'name'
    )


class Arg(Generic[V]):
    """Representation of a command argument."""

    #: The argument's description.
    description: str

    #: The argument's name.
    name: str

    #: The argument's parser.
    parser: Parser[V]

    def __init__(self, description: str, name: str, parser: Parser[V] | None = None) -> None:
        """Initialize this argument.

        :param description: Description of the argument.
        :param name: Name of the argument. :code:`str.lower` will be called on this argument.
        :param parser: Parser for the argument. If omitted,
        :raise KeywordCommandsError: If name does not contain only letters, numbers, and hyphens.
        """
        self.description = description
        if not util.VALID_WORD.fullmatch(name):
            raise ArgInitContext.MalformedName(name=name)
        self.name = name.lower()
        self.parser = parser or Parser.DEFAULT
