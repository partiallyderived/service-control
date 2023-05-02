from collections.abc import MutableMapping, Set

import enough
from enough import EnumErrors, JSONType
from enough.exceptions import EnoughError

import servicecontrol.core.registrar as registrar
from servicecontrol.core._exception import ServiceControlError
from servicecontrol.core.service import Service


class ServiceSpecErrors(EnumErrors[ServiceControlError]):
    """Exception types raised in servicecontrol.core.servicespec."""
    MissingClass = (
        'At least one of "$class" or "$name" must be specified.', 'config'
    )
    MissingName = (
        'No given or default name for service {service.cls_name()}',
        ('service', 'config')
    )
    NoSuchDependency = (
        'The following keys were specified as dependency overrides but are not '
            'recognized by the service class {service.cls_name()} and thus '
            'could not be overridden: {", ".join(names)}',
        ('names', 'service', 'config')
    )
    NoSuchExport = (
        'The following keys were specified as export overrides but are not '
            'recognized by the service class {service.cls_name()} and thus '
            'could not be overridden: {", ".join(names)}',
        ('names', 'service', 'config')
    )
    NoSuchService = 'No services are registered with the name "{name}".', 'name'
    NotAService = (
        '{_enough.fqln(cls)} is not a subclass of servicecontrol.core.Service.',
        'cls',
        TypeError
    )
    ServiceImport = (
        'Failed to import service class {name}: {_error_tb}',
        ('name', 'error'),
        ImportError
    )


class ServiceSpec:
    """Represents a specification for a :class:`.Service`."""

    #: The service class.
    cls: type[Service]

    #: The configuration for the service.
    config: JSONType

    #: Mapping from overridden dependency names to the names to override with
    #: for the service.
    dep_overrides: dict[str, str]

    #: Mapping from overridden export names to the names to override with for
    #: the service.
    export_overrides: dict[str, str]

    #: The name configured for this service, if it was given, or else the
    #: default name.
    name: str

    def _check_unrecognized(
        self, recognized: Set[str],
        overrides: Set[str],
        exc_type: ServiceSpecErrors
    ) -> None:
        # Helper function to handle unrecognized overrides.
        unrecognized = {x for x in overrides if x not in recognized}
        if unrecognized:
            raise exc_type(
                config=self.config,
                names=unrecognized,
                service=self.cls
            )

    def _resolve_class_and_name(
        self, cls_name: str | None, name: str | None
    ) -> None:
        if not cls_name:
            # When $class is not specified, check the registrar.
            if not name:
                raise ServiceSpecErrors.MissingClass(config=self.config)
            cls = registrar.find(name)
            if not cls:
                raise ServiceSpecErrors.NoSuchService(name=name)
        else:
            with ServiceSpecErrors.ServiceImport.wrap_error(
                EnoughError, name=cls_name
            ):
                cls = enough.typed_import(cls_name, type)
        if not issubclass(cls, Service):
            raise ServiceSpecErrors.NotAService(cls=cls)
        self.cls = cls
        self.name = name or self.cls.default_name()
        if self.name is None:
            raise ServiceSpecErrors.MissingName(
                service=self.cls, config=self.config
            )

    def _validate(self, config: JSONType) -> None:
        # Validate the service class and the given configuration for it.
        self.cls.check_init()
        self.cls.validate(config)

    def __init__(self, config: JSONType) -> None:
        """Initializes a :class:`.ServiceSpec` from the given config.

        :param config: Config to initialize with.
        :raise ServiceControlError: If any of the following are true:
            * Neither "$class" nor "$name" are specified in ``config``.
            * If "$name" is not specified in ``config`` and the configured
              service does not have a default name.
            * If the given or inferred class is not a subclass of
              :class:`.Service`.
            * If a dependency or export override is specified for a dependency
              or export which is not recognized by the configured service.
            * If "$name" is specified and "$class" is not, but the configured
              name does not correspond to a registered service.
            * If the class given in "$class" could not be imported.
        """
        cls_name = config.pop('$class', None)
        name = config.pop('$name', None)
        dep_overrides = config.pop('$dep-overrides', {})
        export_overrides = config.pop('$export-overrides', {})
        self.config = config
        try:
            self._resolve_class_and_name(cls_name, name)

            self.dep_overrides = dep_overrides
            self.export_overrides = export_overrides

            self._check_unrecognized(
                self.cls.dep_names(),
                self.dep_overrides.keys(),
                ServiceSpecErrors.NoSuchDependency
            )
            self._check_unrecognized(
                self.cls.export_names(),
                self.export_overrides.keys(),
                ServiceSpecErrors.NoSuchExport
            )

            # Validate the service.
            self._validate(config)
        except Exception:
            # Put config back in its original state.
            for key, val in [
                ('$class', cls_name),
                ('$name', name),
                ('$dep-overrides', dep_overrides),
                ('$export-overrides', export_overrides)
            ]:
                if val is not None and val != {}:
                    config[key] = val
            raise

    def __call__(self, exports: MutableMapping[str, object]) -> Service:
        """Creates a :class:`.Service`, passing the given keyword arguments to
        that service's constructor when they occur in ``self.deps``.

        :param exports: Mapping from names to objects exported by services
            initialized so far. Modified to include objects exported by the
            service with the export names as keys, or overridden names as keys
            when export overrides are configured.
        :return: The resulting service.
        """

        # Only include objects in self.cls.deps().
        # Note that the original dependency name has to be mapped to the value
        # of the overridden name if specified.
        kwargs = {
            d: exports[self.dep_overrides.get(d, d)]
            for d in self.cls.dep_names()
        }
        assert issubclass(self.cls, Service)  # This line makes PyCharm happy.
        # noinspection PyArgumentList
        service = self.cls(self.config, **kwargs)
        service.name = self.name
        for name, obj in service.exports().items():
            # Similarly, the overridden export name if configured has to be
            # mapped to the exported object instead of the original name.
            exports[self.export_overrides.get(name, name)] = obj
        return service

    def cls_name(self) -> str:
        """Gives the fully-qualified class name of the service this spec is for.

        :return: The service's fully-qualified class name.
        """
        return enough.fqln(self.cls)

    def dep_names(self) -> set[str]:
        """Gives the dependency names for the service, taking into account
        overrides.

        :return: The dependency names for the service.
        """
        return {self.dep_overrides.get(d, d) for d in self.cls.dep_names()}

    def export_names(self) -> set[str]:
        """Gives the exported object names for the service, taking into account
        overrides.

        :return: The exported object names for the service.
        """
        return {
            self.export_overrides.get(e, e) for e in self.cls.export_names()
        }
