from __future__ import annotations

import inspect
import typing
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Set
from inspect import Parameter
from typing import ClassVar, Generic, final

from enough import EnumErrors, T

from keywordcommands._exceptions import (
    CommandErrors, KeywordCommandsError, WrappedException
)
from keywordcommands.arg import Arg
from keywordcommands.example import Example
from keywordcommands.node import _CommandNode
from keywordcommands.parser import ParseError
from keywordcommands.typevars import S

if typing.TYPE_CHECKING:
    from keywordcommands.state import CommandState


class CommandInitErrors(EnumErrors[KeywordCommandsError]):
    """Exception types raised in keywordcommands.command."""
    BadExample = (
        'Failed to parse example args for this command: {error}',
        ('args', 'error', 'example')
    )
    ExtraArgs = (
        'The following arguments appear in the argument list for the command '
            'function do not correspond to the names of any Arg instances '
            'passed to Command.__init__: {", ".join(extra)}',
        ('args', 'extra', 'fn')
    )
    MissingArgs = (
        'The following arguments were passed to Command.__init__ but do not '
            'appear as arguments in the command function: {", ".join(missing)}',
        ('args', 'missing', 'fn')
    )
    NonStatePosArg = (
        'The positional argument list of the command function must be exactly '
            '["state"].',
        'fn'
    )
    UppercasedArgs = (
        'The following arguments in the argument list for the command function '
            'have uppercased characters, which is not allowed since arguments '
            'are case-insensitive and are required to be lowercased to avoid '
            'name collisions: {", ".join(upper)}',
        ('upper', 'fn')
    )
    VariadicArg = (
        'Command functions may not have variadic arguments (found {arg}).',
        ('arg', 'fn')
    )


class ExecutionError(KeywordCommandsError):
    """Base class of exceptions which should be raised by :class:`.Command`
    functions to give descriptive error messages."""


class ChainedExecutionError(ExecutionError, WrappedException):
    """Raised when an :class:`.ExecutionException` is caused by another
    error.
    """


@final
class Command(_CommandNode, Generic[S]):
    """Represents a command."""
    # State which serves as a placeholder when there is no available state.
    __void_state: ClassVar[CommandState | None] = None

    # The function to call with the parsed arguments.
    _fn: Callable[[S, ...], object]

    # Optional argument names.
    _optional: Set[str]

    #: Mapping from argument names to their respective arguments.
    args: OrderedDict[str, Arg]

    #: A description of the command.
    description: str

    #: The examples to use to demonstrate the usage of this command.
    examples: Iterable[Example]

    @staticmethod
    def _void_state() -> CommandState:
        # Gives a CommandState with no information. For use so that parsing
        # errors raised in the course of calling _check_examples can be safely
        # raised. Also useful for testing when we do not want to create a
        # fully-fledged CommandState.
        if Command.__void_state:
            return Command.__void_state

        from keywordcommands.group import CommandGroup
        from keywordcommands.state import CommandState
        result = CommandState('', CommandGroup(''))
        result.query.path = []
        result.query.text = ''
        Command.__void_state = result
        return result

    def _check_examples(self, args: Iterable[Arg]) -> None:
        # Try to parse examples to make sure this can be done without error.
        # Args is passed solely for creating an exception if needed.
        for x in self.examples:
            if not x.unchecked:
                with CommandInitErrors.BadExample.wrap_error(
                    Exception, args=args, example=x
                ):
                    self.parse(None, x.kwargs)

    def _check_signature(self, args: Iterable[Arg]) -> None:
        # Check that the supplied function has a signature appropriate for
        # taking in the configured arguments. Args is passed solely for creating
        # an exception if needed.
        pos_args = []
        kwargs = set()
        has_upper_case = []

        sig = inspect.signature(self._fn)
        for name, param in sig.parameters.items():
            if name != name.lower():
                has_upper_case.append(name)
            match param.kind:
                case (
                    Parameter.POSITIONAL_ONLY | Parameter.POSITIONAL_OR_KEYWORD
                ):
                    pos_args.append(name)
                case Parameter.KEYWORD_ONLY:
                    kwargs.add(name)
                case Parameter.VAR_KEYWORD | Parameter.VAR_POSITIONAL:
                    raise CommandInitErrors.VariadicArg(arg=name, fn=self._fn)
                case _:
                    assert False

        if pos_args != ['state']:
            raise CommandInitErrors.NonStatePosArg(fn=self._fn)

        if has_upper_case:
            raise CommandInitErrors.UppercasedArgs(
                fn=self._fn, upper=has_upper_case
            )

        # Underscores in the function argument names translate to hyphens in the
        # user arg names.
        extra_args = [a for a in kwargs if a.replace('_', '-') not in self.args]
        if extra_args:
            raise CommandInitErrors.ExtraArgs(
                args=args, extra=extra_args, fn=self._fn
            )

        missing_args = [
            a for a in self.args if a.replace('-', '_') not in kwargs
        ]
        if missing_args:
            raise CommandInitErrors.MissingArgs(
                args=args, missing=missing_args, fn=self._fn
            )

    def __init__(
        self,
        description: str,
        fn: Callable[[S, ...], object],
        *,
        args: Iterable[Arg] = (),
        examples: Iterable[Example] = ()
    ) -> None:
        """Initializes this command with the given arguments.

        :param description: Description of the command.
        :param fn: Function to call with the parsed arguments.
        :param args: Arguments to be recognized by this command.
        :param examples: Usage examples for this command.
        :raise KeywordCommandsError: If any of the following are true:
            * A checked example fails to be parsed.
            * The positional argument list for ``fn`` is not exactly
              ``['state']``.
            * Names of keyword argument in ``fn`` do not correspond to names of
              arguments in ``args``.
            * Any strings appear as names of arguments in ``args`` but not as
              keyword arguments in ``fn``.
            * Any arguments in ``fn`` have uppercased characters.
            * ``fn`` takes any variadic arguments.
        """
        self.description = description
        self._fn = fn
        self.examples = examples

        # Use OrderedDict in case the argument order is intentional.
        self.args = OrderedDict((a.name, a) for a in args)
        self._optional = (
            inspect.getfullargspec(self._fn).kwonlydefaults or {}
        ).keys()

        self._check_signature(args)
        self._check_examples(args)

    @property
    def optional_args(self) -> list[Arg]:
        """Gives the optional arguments for this command.

        :return: The optional arguments.
        """
        return [a for a in self.args.values() if a.name in self._optional]

    @property
    def required_args(self) -> list[Arg]:
        """Gives the required arguments for this command.

        :return: The required arguments.
        """
        return [a for a in self.args.values() if a.name not in self._optional]

    def __call__(
        self, state: CommandState | None, kwargs: Mapping[str, object]
    ) -> None:
        """Executes this command with the given arguments.

        :param state: State which may contain objects required or useful for
            execution. ``None`` is allowed for the purpose of checking examples.
        :param kwargs: Parsed arguments to execute with.
        :raise KeywordCommandsError: If an error occurs when trying to parse
            arguments or if the command fails to execute.
        """
        state = state or self._void_state()
        try:
            self._fn(state, **kwargs)
        except ExecutionError as e:
            raise CommandErrors.ExecutionError(error=e, query=state.query)

    def arg(self, name: str) -> Arg[T] | None:
        """Get the argument with the given name.

        :param name: Name of the argument to get. Case-insensitive.
        :return: The resulting :class:`.Arg` instance, or ``None`` if no
            argument named ``name`` could be found.
        """
        return self.args.get(name.lower())

    def parse(
        self, state: CommandState | None, kwargs: Mapping[str, str]
    ) -> dict[str, object]:
        """Attempts to parse the arguments for this command.

        :param state: Current command state. ``None`` is allowed for the purpose
            of checking examples.
        :param kwargs: The arguments to parse.
        :return: The parsed arguments.
        :raise KeywordCommandsError: If any of the following are true:
            * One or more unrecognized arguments are supplied.
            * One or more required arguments are missing.
            * An argument fails to be parsed.
        """
        state = state or self._void_state()
        unrecognized = {k for k in kwargs.keys() if k.lower() not in self.args}
        if unrecognized:
            raise CommandErrors.UnrecognizedArgs(
                unrecognized=unrecognized, query=state.query
            )
        # Required - given.
        missing = self.args.keys() - self._optional - kwargs.keys()
        if missing:
            raise CommandErrors.MissingRequiredArgs(
                missing=missing, query=state.query
            )
        parsed = {}

        for k, v in kwargs.items():
            arg = self.args[k]
            with CommandErrors.ParseError.wrap_error(
                ParseError, arg=arg, query=state.query, value=v
            ):
                # Map hyphens to underscores.
                parsed[k.replace('-', '_')] = self.args[k].parser(v, state)
        return parsed

    def tree(self) -> dict[str, None]:
        """Gives a tree where the strings are directed edges,
        :class:`CommandGroups <.CommandGroup>` are the non-leaf vertices, and
        :class:`Commands <.Command>` are the leaf vertices.
        :class:`Commands <.Command>` are leaf nodes and therefore have no edges
        directed from them.

        :return: ``{}``
        """
        return {}


def command(
    description: str, *, args: Iterable[Arg], examples: Iterable[Example]
) -> Callable[[Callable[[S, ...], object]], Command]:
    """Decorator factory whose values can be used to convert a function into a
    :class:`Command`.

    :param description: Description of the command.
    :param args: Arguments to be recognized by this command.
    :param examples: Usage examples for this command.
    :return: A callable which creates a :class:`Command` when called with a
        function.
    """
    return lambda fn: Command(description, fn, args=args, examples=examples)
