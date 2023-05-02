import itertools
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from string import Formatter

import pytest
from _pytest._code import ExceptionInfo as PyTestExceptionInfo

from enough._exception import EnoughError
from enough.enumerrors import EnumErrors
from enough.types import E, T, T1, T2

# Type of cycle information to format CircularDepError with.
_CycleInfo = tuple[Iterable[T], T]


class EnoughFuncErrors(EnumErrors[EnoughError]):
    """Exception types raised in enough.fn."""
    CircularDependency = (
        'Circular object dependency detected as follows (A <- B means A '
            'depends on B): {" <- ".join(str(x) for x in path)}',
        'path',
        ValueError
    )


def _dag_stages_visit(
    obj: T,
    dependency_map: dict[T, set[T]],
    visiting: set[T],
    obj_to_stage: dict[T, int]
) -> _CycleInfo | None:
    # Visit object in a depth-first search fashion in order to calculate the dag
    # stages.
    # The returned tuple contains information about a detected cycle and is
    # comprised of a partial path for which there is a cycle and the object
    # which was twice visited. When this information is propagated upward,
    # objects are appended to complete this path until we propagate to the
    # twice-visited object (this is guaranteed to happen), after which the
    # necessary information to describe the cycle has been gathered and a
    # CircularDependencyException is raised.

    # An object for which _dag_stages_visit is called should never be in visited
    # or obj_to_stage.
    assert obj not in visiting
    assert obj not in obj_to_stage

    stage = 0
    visiting.add(obj)
    for dep in dependency_map[obj]:
        if dep not in obj_to_stage:
            if dep in visiting:
                # If we visit an object that has already been visited, that
                # implies there is a cycle.
                # Indicate a circular dependency by returning a value that will
                # be used to build an error message.
                return [obj, dep], dep
            cycle_info = _dag_stages_visit(
                dep, dependency_map, visiting, obj_to_stage
            )
            if cycle_info:
                graph_path, twice_visited = cycle_info
                graph_path = itertools.chain.from_iterable([[obj], graph_path])
                if obj == twice_visited:
                    graph_path = list(graph_path)
                    # Should always be true.
                    assert graph_path[-1] == obj
                    raise EnoughFuncErrors.CircularDependency(graph_path)
                # Keep propagating the cycle path.
                return graph_path, twice_visited
        stage = max(stage, obj_to_stage[dep] + 1)
    visiting.remove(obj)
    obj_to_stage[obj] = stage
    del dependency_map[obj]
    return None


def bounds(val: T, coll: Iterable[T]) -> tuple[T, T]:
    """Given a collection, determine the upper and lower bounds of the given
    value. Assuming comparison operators are implemented correctly,
    ``bounds(val, coll) == (val, val)`` if and only if ``val in coll``. Does not
    assume that ``coll`` is sorted.

    :param val: Value to get bounds for.
    :param coll: Collections to get bounds in.
    :return: (lower bound or ``None`` if ``val`` is less than all elements in
        ``coll``, upper bound or ``None`` if ``val`` is greater than all
        elements in ``coll``)
    """
    max_lower = None
    min_upper = None
    for x in coll:
        if x <= val and (max_lower is None or x > max_lower):
            max_lower = x
        # Important not to use elif here in case x == val.
        if x >= val and (min_upper is None or x < min_upper):
            min_upper = x
    return max_lower, min_upper


def concat(seq1: Iterable[T], seq2: Iterable[T]) -> list[T]:
    """Concatenates two iterables into a single ``list``.

    :param seq1: First iterable.
    :param seq2: Second iterable.
    :return: The resulting ``list``.
    """
    return list(itertools.chain.from_iterable([seq1, seq2]))


def dag_stages(dependency_map: Mapping[T, Iterable[T]]) -> list[set[T]]:
    """Given a mapping of an object to its like-typed dependencies, compute a
    series of "stages" in which objects in each stage depend only on objects in
    previous stages.

    :param dependency_map: Mapping to compute stages for.
    :return: The computed stages.
    :raise EnoughError: If any objects in ``dependency_map`` are mutually
        dependent.
    """

    # This will be a mapping from objects to their stage index.
    obj_to_stage = {}
    all_objects = set()
    new_dep_map = {}
    for obj, deps in dependency_map.items():
        all_objects.add(obj)
        [all_objects.add(o) for o in deps]
        if not deps:
            # May as well go ahead and init the depth for this object at 0. Also
            # consisted for how unlisted objects are treated.
            obj_to_stage[obj] = 0
        else:
            new_dep_map[obj] = set(deps)
    for obj in all_objects - dependency_map.keys():
        # Treat unlisted objects (those not in dependency_map) as having no
        # dependencies.
        obj_to_stage[obj] = 0
    visiting = set()  # Nodes we are in the process of visiting.

    while new_dep_map:
        obj = next(iter(new_dep_map))
        # A CircularDependencyError should have been raised if the cycle info is
        # not None.
        assert (
            _dag_stages_visit(obj, new_dep_map, visiting, obj_to_stage) is None
        )

    # Use obj_to_stage to create the stages.
    stages = []
    for obj, stage in obj_to_stage.items():
        for _ in range(len(stages), stage + 1):
            stages.append(set())
        stages[stage].add(obj)
    return stages


def flatten(coll: Iterable[Iterable[T]]) -> Iterable[T]:
    """Flattens the given collection of collections into a collection of
    elements.

    :param coll: Collection to flatten.
    :return: The flattened collection.
    """
    return [x for items in coll for x in items]


def format_fields(fmt: str) -> set[str]:
    """Returns the names of all format fields in ``fmt``.

    :param fmt: String to find format fields for.
    :return: The found fields.
    """
    return {
        field for _, field, _, _ in format_fields.formatter.parse(fmt)
        if field is not None
    }


format_fields.formatter = Formatter()


def fqln(cls: type) -> str:
    """Gets the fully-qualified name for a class.

    :param cls: Class to get fully-qualified name for.
    :return: The fully-qualified name for the class.
    """
    return f'{cls.__module__}.{cls.__qualname__}'


def identity(x: T) -> T:
    """Returns the given argument.

    :param x: Value to return.
    :return: ``x``
    """
    return x


def format_table(
    table: Iterable[tuple[T1, Iterable[T2]]],
    *,
    row_sep: str = '\n',
    col_sep: str = ', ',
    key_sep: str = ': ',
    key_fn: Callable[[T1], object] = identity,
    val_fn: Callable[[T2], object] = identity
) -> str:
    """Formats a table with labeled rows.

    :param table: Table to format.
    :param row_sep: String to use to separate rows.
    :param col_sep: String to use to separate columns.
    :param key_sep: String to use to separate keys from elements.
    :param key_fn: Function to use to map keys.
    :param val_fn: Function to use to map elements.
    :return: The formatted table.
    """
    return row_sep.join(
        f'{key_fn(k)}{key_sep}{col_sep.join(str(val_fn(v)) for v in values)}'
        for k, values in table
    )


@contextmanager
def raises(
    exc: E | type[E], *args: object, **kwargs: object
) -> PyTestExceptionInfo[E]:
    """Wrapper around ``pytest.raises`` which may take an ``Exception`` instance
    instead of a type. If this is the case, the raised exception is tested for
    equality against the given exception. Primarily intended to be used in
    conjunction with :class:`KWErrors <.KWError>` ``Exception.__eq__ is
    object.__eq__`` (that is, for two exceptions
    ``exc1`` and ``exc2``, ``exc1 == exc2`` if and only if ``exc1 is exc2``).

    :param exc: Exception or exception type to expect.
    :param args: Additional positional arguments to pass to ``pytest.raises``.
    :param kwargs: Keyword arguments to pass to ``pytest.raises``.
    :return: The ``pytest`` exception info object.
    """
    exc_type = type(exc) if isinstance(exc, Exception) else exc
    with pytest.raises(exc_type, *args, **kwargs) as exc_info:
        yield exc_info
    if isinstance(exc, Exception) and exc_info.value != exc:
        raise AssertionError(f'{exc_info.value!r} was not equal to {exc!r}')
