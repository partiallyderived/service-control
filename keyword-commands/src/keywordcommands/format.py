import traceback
from abc import abstractmethod, ABC
from collections.abc import Callable, Iterable, Mapping, Sequence, Set

import enough
from enough import EnumErrors
from enough.exceptions import EnoughFuncErrors

import keywordcommands.util as util
from keywordcommands._exceptions import CommandErrors, KeywordCommandsError
from keywordcommands.arg import Arg
from keywordcommands.command import Command
from keywordcommands.example import Example
from keywordcommands.group import CommandGroup
from keywordcommands.query import QueryInfo, QueryResult


class FormatErrors(EnumErrors[KeywordCommandsError]):
    """Exception types raised in keywordcommands.format."""
    CircularDependency = EnoughFuncErrors.CircularDependency._value_
    ComposeFieldNameCollision = (
        'Could not compose formats: the following fields are specified both as '
            'formats to be composed and formats to be ignored: '
            '{", ".join(colliding)}',
        'colliding'
    )
    ComposeMissingFields = (
        'The following format fields were not specified as keys in the given '
            'mapping and were not specified as ignored fields: '
            '{", ".join(missing)}',
        'missing'
    )
    FormatterFieldNameCollision = (
        '{_error_prefix}: The following format fields are keys in field_to_fmt '
            'and fmt_fns: {", ".join(colliding)}',
        ('colliding',)
    )
    FormatterMissingFields1 = (
        '{_error_prefix}: The following fields specified in result_to_field '
            'are missing from field_to_fmt: {", ".join(missing)}',
        'missing'
    )
    FormatterMissingFields2 = (
        '{_error_prefix}: The following format fields are present as format '
            'fields in the values of field_to_format but could not be found in '
            'field_to_format.keys() or fmt_fns.keys(): {", ".join(missing)} ',
        'missing'
    )
    MissingResultFields = (
        '{_error_prefix}: One or more QueryResults are missing an associated '
            'format string: {", ".join(result.name for result in missing)}',
        'missing'
    )
    NoResult = (
        'Cannot format a user message for a query which has no result.', 'query'
    )

    @property
    def _error_prefix(cls) -> str:
        return 'Failed to create DefaultQueryFormatter'


def compose_fmts(
    field_to_fmt: Mapping[str, str],
    *,
    ignore: Set[str] = frozenset()
) -> dict[str, str]:
    """Given a mapping from format field keys to format strings, treat the
    expansion of each format string with its required fields as the value that
    its format key in the supplied mapping should be expanded to for other
    format strings in the mapping. In this way, format strings are dependent on
    other format strings whose format field key appears as a format field in the
    dependent format string. The algorithm returns successfully when all the
    given format strings are successfully expanded except for format fields
    specified in ``ignore``.

    :param field_to_fmt: Mapping from format field keys to the format strings
        whose expansions are to be their values.
    :param ignore: Format fields to leave untouched in the given format strings.
    :return: Mapping from format field keys to their expanded values.
    :raise KeywordCommandsError: If any of the following are true:
        * A format field is found in both ``field_to_fmt`` and ``ignore``.
        * A format field is found in a given format string which is not a key in
            ``field_to_fmt`` or an element in ``ignore``.
        * Two or more distinct format strings are found to be mutually
            dependent.
    """
    # Use these kwargs for every substitution to preserve ignored format fields.
    ignore_kwargs = {k: f'{{{k}}}' for k in ignore}
    ignored_and_included = ignore & field_to_fmt.keys()
    if ignored_and_included:
        raise FormatErrors.ComposeFieldNameCollision(
            colliding=ignored_and_included
        )
    # This will be a mapping from format fields to the format fields they are
    # dependent on as inferred from their format string.
    dependency_map = {k: [] for k in field_to_fmt}
    missing_fields = set()
    for field, fmt in field_to_fmt.items():
        for sub_field in enough.format_fields(fmt):
            if sub_field not in field_to_fmt:
                if sub_field not in ignore:
                    missing_fields.add(sub_field)
            else:
                dependency_map[field].append(sub_field)
    if missing_fields:
        raise FormatErrors.ComposeMissingFields(missing=missing_fields)
    expanded = {}
    # Iterate over every stage of of format field, where in each stage, their
    # corresponding format strings only require the expansion of format strings
    # in previous stages. Therefore, they can be expanded stage-wise.
    with FormatErrors.CircularDependency.wrap(
        EnoughFuncErrors.CircularDependency
    ):
        stages = enough.dag_stages(dependency_map)
    for stage in stages:
        for field in stage:
            fmt = field_to_fmt[field]
            expanded[field] = fmt.format(**expanded, **ignore_kwargs)
    return expanded


def default_field_to_fmt() -> dict[str, str]:
    """Provides a default mapping for use as the ``field_to_fmt`` argument in
    :meth:`.DefaultQueryFormatter.__init__`.

    :return: The default mapping.
    """
    return {
        'app_err': '"{app}" failed',
        'args_info':
            'Here are all the arguments recognized by "{path}":\n{args}',
        'args': '{required}\n{optional}',
        'cmd_err': 'Failed to run "{path}"',
        'cmd_help':
            '"{path}" {cmd_desc}\n\n'
            '{examples}\n\n'
            '{args}\n\n'
            '{gen_help_info}',
        'cmd_help_info':
            'For more information about "{path}", type "{app} help {path}"',
        'duplicate_args_err':
            '{app_err}: {duplicate_args_err_reason}\n\n{gen_help_info}',
        'duplicate_args_err_reason':
            'The following arguments were specified more than once: '
            '{duplicated_args}',
        'exe_err': '{cmd_err}: {error}\n\n{cmd_help_info}',
        'gen_help': '"{app}" {root_desc}\n\n{root_cmds_help}',
        'gen_help_info':
            'For more information about commands in general, type "{app} '
            'help".',
        'group_cmds_help':
            'Here is a short description of every command under '
            '"{path}":\n{cmds}',
        'group_help':
            '"{path}" {group_desc}\n\n{group_cmds_help}\n\n{gen_help_info}',
        'help_not_found':
            'Could not get help information for "{path}" because it is not a '
            'valid command or group of commands. '
            '{root_cmds_help}\n\n{gen_help_info}',
        'missing_args_err':
            '{cmd_err}: {missing_args_reason}\n\n{missing_args_info}',
        'missing_args_info':
            'The following arguments are required for '
            '"{path}":\n{required_args}\n\n{cmd_help_info}',
        'missing_args_reason':
            'The following required arguments were not given: {missing_args}',
        'missing_path_err':
            '{app_err}: {missing_path_reason}\n\n{gen_help_info}',
        'missing_path_reason':
            'Keyword arguments were specified but a command was not.',
        'not_found_err': '{app_err}: {not_found_reason}\n\n{not_found_info}',
        'not_found_info':
            'Here is a short description of all available commands:\n'
            '{root_cmds}\n\n{gen_help_info}',
        'not_found_reason': '"{path}" is not a valid command.',
        'not_a_cmd_err':
            '{app_err}: {not_a_cmd_reason}\n\n{group_cmds_help}\n\n'
            '{gen_help_info}',
        'not_a_cmd_reason':
            '"{path}" cannot be run because it is not a command but a group of '
            'commands.',
        'optional': 'Optional Arguments:\n{indented_optional_args}',
        'parse_err': '{cmd_err}: {parse_err_reason}\n\n{parse_err_info}',
        'parse_err_info': '{args_info}\n\n{cmd_help_info}',
        'parse_err_reason':
            'Expected {err_expected} for the value of {err_arg}, found '
            '{err_actual}.',
        'required': 'Required Arguments:\n{indented_required_args}',
        'root_cmds_help':
            'Here is a short description of every available command:\n'
            '{root_cmds}',
        'unexpected_err': '{cmd_err}: {unexpected_reason}',
        'unexpected_reason':
            'An unexpected error occurred, please try again. If the problem '
            'persists, share this message to get help: {unexpected}',
        'unrecognized_args_err':
            '{cmd_err}: {unrecognized_args_reason}\n\n{unrecognized_args_info}',
        'unrecognized_args_info': '{args_info}\n\n{cmd_help_info}',
        'unrecognized_args_reason':
            'The following arguments were not recognized: {unrecognized_args}',
    }


def default_result_to_field() -> dict[QueryResult | CommandErrors, str | None]:
    """Provides a default mapping for use as the ``result_to_field`` argument in
    :meth:`.DefaultQueryFormatter.__init__`.

    :return: The default mapping.
    """
    return {
        QueryResult.SUCCESS: None,
        QueryResult.GENERAL_HELP: 'gen_help',
        QueryResult.GROUP_HELP: 'group_help',
        QueryResult.CMD_HELP: 'cmd_help',
        QueryResult.HELP_NOT_FOUND: 'help_not_found',
        CommandErrors.NoSuchPath: 'not_found_err',
        CommandErrors.NotCommand: 'not_a_cmd_err',
        CommandErrors.DuplicateArgs: 'duplicate_args_err',
        CommandErrors.MissingPath: 'missing_path_err',
        CommandErrors.MissingRequiredArgs: 'missing_args_err',
        CommandErrors.UnrecognizedArgs: 'unrecognized_args_err',
        CommandErrors.ParseError: 'parse_err',
        CommandErrors.ExecutionError: 'exe_err',
        CommandErrors.UnexpectedError: 'unexpected_err'
    }


class QueryFormatFns(ABC):
    """Base class whose implementations provide functions for formatting
    components of format strings using a :class:`QueryInfo` instance.
    """

    @abstractmethod
    def fmt_fns(self) -> Mapping[str, Callable[[QueryInfo], str]]:
        """Provides a mapping from format string fields to functions to call on
        a :class:`QueryInfo` instance to expand them.

        :return: Mapping from format string fields to functions.
        """
        ...


# noinspection PyMethodMayBeStatic
class DefaultQueryFormatFns(QueryFormatFns):
    """Default implementation of :class:`QueryFormatFns`."""

    # The functions to use to expand the format fields.
    _fmt_fns: dict[str, Callable[[QueryInfo], str]]

    def _make_fmt_fns(self) -> dict[str, Callable[[QueryInfo], str]]:
        # Create the functions. Done once during initialization.
        return {
            'app': lambda q: q.name,
            'cmd_desc': lambda q: util.uncapitalize(q.cmd.description),
            'cmds': lambda q: self.fmt_cmds(q.group, q.path),
            'duplicated_args': lambda q: self.fmt_coll(q.error.duplicated),
            'err_actual': lambda q: q.error.value,
            'err_arg': lambda q: q.error.arg.name,
            'err_expected': lambda q: q.error.arg.parser.expected_format,
            'error': lambda q: str(q.error),
            'examples': lambda q: self.fmt_examples(q.cmd.examples, q.path),
            'group_desc': lambda q: util.uncapitalize(q.group.description),
            'indented_optional_args': lambda q: self.fmt_args(
                q.cmd.optional_args, indent=4
            ),
            'indented_required_args': lambda q: self.fmt_args(
                q.cmd.required_args, indent=4
            ),
            'missing_args': lambda q: self.fmt_coll(q.error.missing),
            'path': lambda q: util.expand_path(q.path),
            'optional_args': lambda q: self.fmt_args(
                q.cmd.optional_args, indent=0
            ),
            'required_args': lambda q: self.fmt_args(
                q.cmd.required_args, indent=0
            ),
            'root_cmds': lambda q: self.fmt_cmds(q.root, []),
            'root_desc': lambda q: q.root.description,
            'unexpected': lambda q: self.fmt_unexpected(q.error),
            'unrecognized_args': lambda q: self.fmt_coll(q.error.unrecognized)
        }

    def __init__(self) -> None:
        """Initializes this by creating its format functions."""
        self._fmt_fns = self._make_fmt_fns()

    def fmt_arg(self, arg: Arg) -> str:
        """Formats a single argument in a list of arguments.

        :param arg: The argument to format.
        :return: The formatted argument.
        """
        return (
            f'{arg.name}: {arg.description} Expected value: '
            f'{arg.parser.expected_format}'
        )

    def fmt_args(self, args: Sequence[Arg], indent: int) -> str:
        """Formats the given arguments.

        :param args: Arguments to format.
        :param indent: How much to indent each argument by.
        :return: The formatted arguments.
        """
        indention = ' ' * indent
        return '\n'.join(f'{indention}{self.fmt_arg(a)}' for a in args)

    def fmt_cmd_short(self, cmd: Command, path: Sequence[str]) -> str:
        """Formats a short description of the given command.

        :param cmd: Command to format.
        :param path: Path to the command.
        :return: The formatted command.
        """
        return f'{util.expand_path(path)}: {cmd.description}'

    def fmt_cmds(self, group: CommandGroup, path: Sequence[str]) -> str:
        """Formats the commands in the given group.

        :param group: Group for which commands should be formatted.
        :param path: Path to the given group.
        :return: The formatted commands.
        """
        cmds_with_full_paths = [
            (enough.concat(path, sub_path), cmd)
            for sub_path, cmd in group.commands()
        ]
        return '\n'.join(
            self.fmt_cmd_short(cmd, pth) for pth, cmd in cmds_with_full_paths
        )

    def fmt_coll(self, coll: Iterable[str]) -> str:
        """Formats the given collection of strings.

        :param coll: Collection to format.
        :return: The formatted collection.
        """
        return ', '.join(coll)

    def fmt_example(self, example: Example, path: Sequence[str]) -> str:
        """Formats a single example within a list of examples.

        :param example: The example to format.
        :param path: The path to the command the example is for.
        :return: The formatted example.
        """
        return f'Example: "{example.expand(path)}" {example.description}'

    def fmt_examples(
        self, examples: Iterable[Example], path: Sequence[str]
    ) -> str:
        """Formats a collection of examples.

        :param examples: The examples to format.
        :param path: Path to the command the examples are for.
        :return: The formatted examples.
        """
        return '\n'.join(self.fmt_example(e, path) for e in examples)

    def fmt_fns(self) -> dict[str, Callable[[QueryInfo], str]]:
        """Provides a mapping from format string fields to functions to call on
        a :class:`QueryInfo` instance to expand them.

        :return: Mapping from format string fields to functions.
        """
        return self._fmt_fns

    def fmt_unexpected(self, unexpected: CommandErrors.UnexpectedError) -> str:
        """Formats an unexpected failure.

        :param unexpected: The unexpected failure.
        :return: The formatted unexpected failure.
        """
        return ''.join(traceback.format_exception(unexpected.error))


class QueryFormatter(ABC):
    """Base class whose implementations provide a method for generating a user
    message from a :class:`QueryInfo` instance.
    """
    @abstractmethod
    def user_msg(self, query: QueryInfo) -> str:
        """Use the given :class:`QueryInfo` instance to format a user message.

        :param query: Query to format a message with.
        :return: The formatted user message.
        """
        ...


class DefaultQueryFormatter(QueryFormatter):
    """Default query formatter implementation builds formatted user messages by
    composed format strings.
    """

    #: The composed format strings, expanded as much as possible without a
    #: :class:`QueryInfo` instance.
    field_to_format: Mapping[str, str]

    #: Mapping from format fields to functions which take in a
    #: :class:`QueryInfo` instance to evaluate those fields.
    fmt_fns: Mapping[str, Callable[[QueryInfo], str]]

    #: Mapping from possible :class:`QueryResults <.QueryResult>` to a format
    #: string to create a user message with.
    #: When a value is ``None``, no message is sent in this situation.
    result_to_field: Mapping[QueryResult, str | None]

    def __init__(
        self,
        field_to_fmt: Mapping[str, str] | None = None,
        fmt_fns: Mapping[str, Callable[[QueryInfo], str]] | None = None,
        result_to_field:
            Mapping[QueryResult | CommandErrors, str | None] | None = None
    ) -> None:
        """Uses the given formatting information to initialize this.

        :param field_to_fmt: Mapping from format fields to the format strings
            they should expand to. If unspecified,
            :func:`default_field_to_fmt()` is used.
        :param fmt_fns: Mapping from format fields to functions to use to format
            :class:`QueryInfo` data. If unspecified,
            :func:`DefaultQueryFormatFns.fmt_fns()` is used.
        :param result_to_field: Mapping from possible
            :class:`QueryResults <.QueryResult>` to a format string to create a
            user message for that result with. If unspecified,
            :func:`default_result_to_field()` is used.
        :raise KeywordCommandsError: If any of the following are true:
            * A format field is a key in both ``field_to_fmt`` and
              ``fmt_fns()``.
            * A format field is found in a given format string which is neither
              a key in ``field_to_fmt`` or an element in ``fmt_fns``, or a value
              in ``result_to_field`` contains a field with this property.
            * One or more result fields are missing in ``result_to_field``.
            * If two or more distinct format strings are found to be mutually
              dependent.
        """
        field_to_fmt = field_to_fmt or default_field_to_fmt()
        fmt_fns = fmt_fns or DefaultQueryFormatFns().fmt_fns()
        result_to_field = result_to_field or default_result_to_field()
        missing_result_fields = (
            (set(QueryResult) | set(CommandErrors)) - set(result_to_field)
        )
        if missing_result_fields:
            raise FormatErrors.MissingResultFields(
                missing=missing_result_fields
            )
        unrecognized_fields = set(
            result_to_field.values()
        ) - field_to_fmt.keys() - {None}
        if unrecognized_fields:
            raise FormatErrors.FormatterMissingFields1(
                missing=unrecognized_fields
            )

        # Ignore keys in fns, since those are expanded by fns instead of by
        # composed format strings.
        try:
            self.field_to_format = compose_fmts(
                field_to_fmt, ignore=fmt_fns.keys()
            )
        # Want different error messages than those for compose_fmts errors.
        except FormatErrors.ComposeFieldNameCollision as e:
            raise FormatErrors.FormatterFieldNameCollision(
                colliding=e.colliding
            )
        except FormatErrors.ComposeMissingFields as e:
            raise FormatErrors.FormatterMissingFields2(missing=e.missing)

        self.fmt_fns = fmt_fns
        self.result_to_field = result_to_field

    def user_msg(self, query: QueryInfo) -> str | None:
        """Use the given :class:`QueryInfo` instance to format a user message.

        :param query: Query to format a message with.
        :return: The formatted user message, or ``None`` if no user message
            should be created.
        :raise KeywordCommandsError: If ``query.result is None``.
        """
        if query.result is None:
            raise FormatErrors.NoResult(query=query)
        field = self.result_to_field[query.result]
        if field is None:
            return None
        fmt = self.field_to_format[field]
        required_fields = enough.format_fields(fmt)
        fmt_kwargs = {k: self.fmt_fns[k](query) for k in required_fields}
        return fmt.format(**fmt_kwargs)
