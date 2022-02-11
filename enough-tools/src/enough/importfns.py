import importlib
import inspect
from types import ModuleType
from typing import Final, TypeGuard

from enough._exception import BRError
from enough.enumerrors import EnumErrors
from enough.types import T


# When getting a modules members, ignore members with these names.
_IGNORED_MEMBERS: Final[frozenset[str]] = frozenset(
    {'__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__', '__spec__'}
)


class BRImportErrors(EnumErrors[BRError]):
    """Exception types raised in bobbeyreese.importfns."""
    CheckFailed = 'Object {obj} failed import check.', 'obj', RuntimeError
    InstanceCheckFailed = 'Object {obj} is not an instance of {type.__name__}', ('obj', 'type'), TypeError
    ModuleImport = 'Failed to import module "{name}": {error}', ('name', 'error'), ImportError
    ObjectNotFound = 'Failed to import name "{name}" from "{module}".', ('name', 'module'), ImportError


def checked_import(fqln: str, predicate: TypeGuard[T]) -> T:
    """Attempts to import an object with the given fully-qualified name and raises an exception if that object fails
    the given predicate.

    :param fqln: Fully-qualified name of object to import.
    :param predicate: Predicate to use to check if the object satisfies a condition.
    :return: The imported object.
    :raise BRError: If the object could not be imported, or if the imported object fails :code:`predicate`.
    """
    obj = import_object(fqln)
    if predicate(obj):
        return obj
    raise BRImportErrors.CheckFailed(obj)


def import_object(fqln: str) -> object:
    """Imports an object with the given name.

    :param fqln: Fully-qualified name of the object to import.
    :return: The imported object.
    :raise BRError: If the module containing the object could not be imported, or if the module could be imported
        but the object could not be found.
    """
    module_name, object_name = fqln.rsplit('.', maxsplit=1)
    with BRImportErrors.ModuleImport.wrap_error(Exception, name=module_name):
        module = importlib.import_module(module_name)
    with BRImportErrors.ObjectNotFound.wrap_error(AttributeError, dest=None, name=object_name, module=module):
        return getattr(module, object_name)


def module_members(module: ModuleType, predicate: TypeGuard[T]) -> list[T]:
    """Gets all of the members of a module which satisfy the given predicate. For the purposes of this function, an
    object :code:`x` is only considered to be a member of :code:`module` if
    :code:`getattr(x, x.__module__, module.__name__) == module.__name__`.

    :param module: Module to find members in.
    :param predicate: Predicate to satisfy.
    :return: The members of :code:`module` satisfying :code:`predicate`.
    """
    return [
        member for name, member in inspect.getmembers(module, predicate)
        if (
            # Ignore members like __doc__ which are found in every module.
            name not in _IGNORED_MEMBERS

            # Use __module__ to determine if the member was originally defined in this module. Assume this is the case
            # if the __module__ attribute is not present.
            and getattr(member, '__module__', module.__name__) == module.__name__
            and predicate(member)
        )
    ]


def typed_import(fqln: str, typ: type[T]) -> T:
    """Attempts to import the object with the given fully-qualified name, and checks that it is of the given type,
    raising an exception if it is not.

    :param fqln: Fully-qualified name of the object to import.
    :param typ: Type to check that the imported object is an instance of.
    :return: The imported object.
    :raise BRError: If the object could not be imported, or if it is not an instance of :code:`typ`.
    """
    with BRImportErrors.InstanceCheckFailed.wrap(BRImportErrors.CheckFailed, type=typ):
        return checked_import(fqln, lambda x: isinstance(x, typ))


def typed_module_members(module: ModuleType, typ: type[T]) -> list[T]:
    """Gets all members of the given module which are instances of the given type.

    :param module: Module to get members from.
    :param typ: Type to check that members are instances of.
    :return: The members of :code:`module` which are instances of :code:`typ`.
    """
    return module_members(module, lambda x: isinstance(x, typ))
