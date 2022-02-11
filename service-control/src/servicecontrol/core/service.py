from __future__ import annotations

import inspect
from abc import ABC
from collections.abc import Iterable
from typing import ClassVar

import enough as br
import jsonschema
from enough import EnumErrors, JSONType
from jsonschema import ValidationError

from servicecontrol.core._exception import ServiceControlError


class ServiceErrors(EnumErrors[ServiceControlError]):
    """Exception types raised in servicecontrol.core.service."""
    NoConfigArg = (
        '"config" excepted as first positional argument after "self" to __init__ method of service'
            '{service.cls_name()}',
        'service',
        TypeError
    )
    NoJobsImplemented = 'No jobs have been implemented for {service.cls_name()}', 'service', NotImplementedError
    SchemaValidation = '{service.cls_name()} failed validation: {_error_tb}', ('service', 'error', 'config')


class Service(ABC):
    """Class representing a service which is managed by a :class:`.Controller`."""

    #: Names of objects exported by this service.
    EXPORTS: ClassVar[Iterable[str]] = frozenset()

    #: When True, this service's exports may be used as dependencies without explicit configuration.
    IMPLICIT: ClassVar[bool] = False

    #: Name of the service. If unspecified, users must supply a name via the '$name' configuration.
    NAME: ClassVar[str | None] = None

    #: JSON Schema to validate configuration with.
    SCHEMA: ClassVar[JSONType] = {}

    #: The name configured for this service.
    name: str

    @classmethod
    def check_init(cls) -> None:
        """Verifies that the __init__ method for this class takes "config" as its first positional argument.

        :raise ServiceControlError: If "config" is not the name of the first positional argument of __init__ for this
            class.
        """
        init_spec = inspect.getfullargspec(cls.__init__)
        if len(init_spec.args) <= 1 or init_spec.args[1] != 'config':
            raise ServiceErrors.NoConfigArg(service=cls)

    @classmethod
    def cls_name(cls) -> str:
        """Gives the fully-qualified name for this service's class.

        :return: The service class's fully-qualified name.
        """
        return br.fqln(cls)

    @classmethod
    def default_name(cls) -> str | None:
        """Gives the default name for this service, if there is one.

        :return The default name for this service if it exists, :code:`None` otherwise.
        """
        return cls.NAME

    @classmethod
    def dep_names(cls) -> set[str]:
        """Gives the objects which this service is dependent on.

        :return: The objects which this service is dependent on.
        """

        # Infer arguments from __init__ for maximum convenience.
        init_spec = inspect.getfullargspec(cls.__init__)
        return set(init_spec.args[2:] + init_spec.kwonlyargs)

    @classmethod
    def export_names(cls) -> set[str]:
        """Gives the names of objects produced by this service.

        :return: The names of objects produced by this service.
        """
        return set(cls.EXPORTS)

    @classmethod
    def implicit(cls) -> bool:
        """Determines whether this is an implicitly usable service.

        :return: :code:`True` if this service is implicitly usable, :code`False` otherwise.
        """
        return cls.IMPLICIT

    @classmethod
    def schema(cls) -> JSONType:
        """Gives the `JSON Schema <https://json-schema.org/>` to validate configuration with.

        :return: The JSON Schema to validate with.
        """
        return cls.SCHEMA

    @classmethod
    def validate(cls, config: JSONType) -> None:
        """Checks that the given config is valid for this service.

        :param config: Config to validate.
        :raise ServiceControlError: If validation for the config fails.
        """
        with ServiceErrors.SchemaValidation.wrap_error(ValidationError, config=config, service=cls):
            jsonschema.validate(config, cls.schema())

    # noinspection PyUnusedLocal
    def __init__(self, config: JSONType) -> None:
        """Initializes a service with the given config.

        :param config: Config to initialize with.
        """
        self.name = ''

    def exports(self) -> dict[str, object]:
        """Gives all the objects exported by this service.

        :return: The objects exported by this service.
        """
        return {n: getattr(self, n) for n in self.EXPORTS}

    def install(self) -> None:
        """Performs environment-related (such as creating files and folders) tasks to be run once in the lifetime of the
        service in which this service is used, unless a re-install of the service is requested.
        """

    def installed(self) -> bool:
        """Determines whether this service is :meth:`installed <.Service.install>`.
        Must be overridden by service which need installation (always returns :code:`True` unless overridden).

        :return: :code:`True` if this service is installed, :code:`False` otherwise.
        """
        return True

    def job(self, *args: str) -> None:
        """Performs a job with the given arguments on this service.

        :param args: The positional arguments to the job.
        :raise ServiceControlError: If no jobs have been implemented for this service.
        """
        raise ServiceErrors.NoJobsImplemented(service=self)

    def purge(self) -> None:
        """Deletes any persistent data created by this service."""
    
    def start(self) -> None:
        """Starts this service."""

    def stop(self) -> None:
        """Stops this service."""
