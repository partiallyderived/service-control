import importlib
import pkgutil
from types import ModuleType
from typing import Final

import enough
from enough import EnumErrors

import servicecontrol
from servicecontrol.core._exception import ServiceControlError
from servicecontrol.core.service import Service

# Mapping from names of exports which have implicitly usable services.
_IMPLICIT_EXPORTS: Final[dict[str, type[Service]]] = {}

# Mapping from service name to the service registered with that name.
_NAME_TO_SERVICE: Final[dict[str, type[Service]]] = {}

# Indicates whether the servicecontrol package has been recursively registered.
_default_registration_done: bool = False


class RegistrationErrors(EnumErrors[ServiceControlError]):
    """Exception types raised in servicecontrol.core.registrar."""
    ImplicitExists = (
        'Failed to register implicit service {service.cls_name()}: the '
            'following objects are already registered as exports for an '
            'implicit service: {", ".join(exports)}',
        ('exports', 'service')
    )
    NotAService = (
        '{_enough.fqln(cls)} is not a subclass of servicecontrol.core.Service.',
        'cls',
        TypeError
    )
    RegistrationExists = (
        'Failed to register service {attempted.cls_name()} with the name '
            '"{name}": The service class {registered.cls_name()} is already '
            'registered with that name.',
        ('name', 'attempted', 'registered')
    )


def find(name: str) -> type[Service] | None:
    """Finds the service which is registered with the given name,
    case-insensitive, or else return ``None``.

    :param name: Name of services to find.
    :return: The classes of services registered with that name.
    """
    return _NAME_TO_SERVICE.get(name.lower())


def find_implicit(name: str) -> type[Service] | None:
    """Finds an implicitly-available service that exports an object with the
    given name.

    :param name: The exported name.
    :return: The implicitly-available service.
    """
    return _IMPLICIT_EXPORTS.get(name)


def recursively_register(package: ModuleType) -> None:
    """Recursively registers all service classes which can be found in the given
    package or any of its subpackages or submodules or any of their submodules
    and subpackages, etc.

    :param package: Name of the package to recurse over.
    """
    for _, mod_name, is_pkg in pkgutil.iter_modules(
        package.__path__, prefix=f'{package.__name__}.'
    ):
        module = importlib.import_module(mod_name)
        register_all_in_module(module)
        if is_pkg:
            recursively_register(module)


def register(name: str, service_type: type[Service]) -> None:
    """Registers a default name for the given service.

    :param name: Name to use.
    :param service_type: The class of the service to register.
    :raise ServiceControlError: If any of the following are true:
        * The service to be registered is implicit but the names of at least one
          of its exports is the same as one for a previously registered implicit
          service.
        * The service to be registered is implicit but the names of at least one
          of its exports is the same as one for a previously registered implicit
          service.
        * A service is already registered with ``name``.
    """
    if not issubclass(service_type, Service):
        raise RegistrationErrors.NotAService(cls=service_type)
    existing = _NAME_TO_SERVICE.get(name)
    if existing:
        raise RegistrationErrors.RegistrationExists(
            attempted=service_type, name=name, registered=existing
        )
    if service_type.implicit():
        existing_implicits = {
            x for x in service_type.export_names() if x in _IMPLICIT_EXPORTS
        }
        if existing_implicits:
            raise RegistrationErrors.ImplicitExists(
                exports=existing_implicits, service=service_type
            )
        for export_name in service_type.export_names():
            _IMPLICIT_EXPORTS[export_name] = service_type
    _NAME_TO_SERVICE[name.lower()] = service_type


def register_all_in_module(module: ModuleType) -> None:
    """Registers all services in the given module which have overridden
    :meth:`.Service.default_name`.

    :param module: Module to register services for.
    """
    for cls in enough.module_members(
        module, lambda m: isinstance(m, type) and issubclass(m, Service)
        and m.default_name() is not None
    ):
        if issubclass(cls, Service) and cls.default_name() is not None:
            register(cls.default_name(), cls)


def register_defaults() -> None:
    """If it has not been done already, recursively registers all services
    contained in the servicecontrol package.
    """
    global _default_registration_done
    if not _default_registration_done:
        # noinspection PyTypeChecker
        recursively_register(servicecontrol)
        _default_registration_done = True
