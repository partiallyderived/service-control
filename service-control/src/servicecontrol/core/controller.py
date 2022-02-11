from collections.abc import Mapping, Sequence
from typing import Final

import enough as br
import jsonschema
from enough import EnumErrors, JSONType
from enough.exceptions import BRFuncErrors
from jsonschema import ValidationError

import servicecontrol.core.registrar as registrar
from servicecontrol.core._exception import ServiceControlError
from servicecontrol.core.service import Service
from servicecontrol.core.servicespec import ServiceSpec

#: This str is shared in two error contexts.
_BASE_MSG: Final[str] = 'Failed to start service {spec.name} ({spec.cls_name}): {_error_tb}'


class ControllerErrors(EnumErrors[ServiceControlError]):
    """Exception types raised in servicecontrol.core.controller."""
    CircularDependency = BRFuncErrors.CircularDependency._value_
    ExportCollision = (
        'The following names belong to objects exported by two or more services:\n\n'
            ''
            '{_br.format_table(collisions.items(), val_fn=lambda spec: spec.name)}\n\n'
            ''
            'Note: You can specify the key "$export-overrides" in service configs as a mapping from exported names '
            'to names to override them with to avoid name collisions.',
        'collisions'
    )
    InitSpecs = (
        'Failed to create specs for the following services:\n\n'
            ''
            '{_fmt_error_map()}',
        'errors'
    )
    JobFailed = (
        'Failed to run job for service "{service.name}" ({service}): {_error_tb}\n'
            'args: {args}',
        ('error', 'service', 'args')
    )
    NameCollision = (
        'The following names refer to multiple services:\n\n'
            ''
            '{_br.format_table(collisions.items(), val_fn=lambda spec: spec.cls_name())}',
        'collisions'
    )
    NoSuchService = 'Could not find service named "{name}"', ('name',)
    PurgeFailed = 'Failed to purge service "{service.name}" ({service}): {_error_tb}', ('service', 'error')
    SchemaValidation = 'Controller config failed JSON validation: {_error_tb}', ('error', 'config')
    ServiceStart = (
        f'{_BASE_MSG}\n\n'
            f''
            f'Previously started services were stopped in reverse order.',
        ('error', 'service', 'spec')
    )
    ServiceStartStop = (
        f'{_BASE_MSG}\n\n'
            f''
            f'Additional failures occurred when attempting to stop already started services in reverse order:\n\n'
            f''
            f'{{_fmt_error_map(lambda service: service.name)}}',
        ('error', 'errors', 'service', 'spec')
    )
    ServiceStop = (
        'Failed to stop the following services:\n\n'
            ''
            '{_fmt_error_map(lambda service: service.name)}',
        'errors'
    )
    UnsatisfiedDependencies = (
        'The following services have unsatisfied dependencies:\n\n'
            ''
            '{_br.format_table(unsatisfied.items(), key_fn=lambda spec: spec.name)}',
        'unsatisfied'
    )


class Controller:
    """Instances of this class control services, including by starting and stopping them and managing their 
    dependencies.
    """
    #: JSON Schema for the controller's config.
    SCHEMA: Final[JSONType] = {
        'description': 'Configuration for service controller.',
        'type': 'object',
        'properties': {
            'services': {
                'description': 'Configurations for services to use.',
                'type': 'array',
                'items': {
                    'description': 'Configuration for a service.',
                    'type': 'object',
                    'anyOf': [
                        {'required': ['$class']},
                        {'required': ['$name']}
                    ],
                    'properties': {
                        '$class': {
                            'description': 'The fully-qualified class name corresponding to the service to use.',
                            'type': 'string'
                        },
                        '$dep-overrides': {
                            'description': 'Mapping from default dependency name to name to override with.',
                            'type': 'object',
                            'additionalProperties': {
                                'description': 'Name to override default dependency name with.',
                                'type': 'string'
                            },
                            'propertyNames': {
                                'pattern': '^[A-Za-z_][A-Za-z0-9_]*$'
                            }
                        },
                        '$export-overrides': {
                            'description': 'Mapping from export default names to name to override with.',
                            'type': 'object',
                            'additionalProperties': {
                                'description': 'Name to override default export name with.',
                                'type': 'string'
                            },
                            'propertyNames': {
                                'pattern': '^[A-Za-z_][A-Za-z0-9_]*$'
                            }
                        },
                        '$name': {
                            'description':
                                'Name of the service. When specified with $class, this name is used to reference the '
                                'service. Otherwise, an attempt is made to infer the desired service from the name. If '
                                'no service could be inferred, config validation fails.',
                            'type': 'string'
                        }
                    }
                }
            },
        },
        'required': ['services'],
        'additionalProperties': False
    }

    #: Mapping from names of services to the service(s) they are a name for.
    name_to_service: dict[str, Service]

    #: The started services, organized into stages whereby services in a later stage depend only on services in a
    #: previous stage, and which depend on at least 1 object in the most recent previous stage.
    service_stages: list[set[Service]]

    #: :class:`ServiceSpecs <.ServiceSpec>` to use to create services, organized into stages as above.
    spec_stages: list[set[ServiceSpec]]

    @staticmethod
    def _check_export_collisions(collisions: dict[str, set[ServiceSpec]]) -> None:
        # If export name collisions exist, raise an ExportCollisionError.
        if collisions:
            raise ControllerErrors.ExportCollision(collisions=collisions)

    @staticmethod
    def _check_name_collisions(specs: Sequence[ServiceSpec]) -> None:
        # Check if there are any name collisions among the ServiceSpecs.
        name_to_specs = {}
        for spec in specs:
            name_to_specs.setdefault(spec.name, set()).add(spec)
        collisions = {k: v for k, v in name_to_specs.items() if len(v) > 1}
        if collisions:
            raise ControllerErrors.NameCollision(collisions=collisions)

    @staticmethod
    def _check_unsatisfied_deps(unsatisfied: dict[ServiceSpec, set[str]]) -> None:
        # If any service dependencies were unsatisfied, raise an UnsatisfiedDependenciesError.
        if unsatisfied:
            raise ControllerErrors.UnsatisfiedDependencies(unsatisfied=unsatisfied)

    @staticmethod
    def _export_to_spec(specs: Sequence[ServiceSpec]) -> dict[str, ServiceSpec]:
        # Create a mapping from exported object names to the service in which they belong.

        # If there are any name collisions, aggregate them here.
        collisions = {}
        result = {}
        for spec in specs:
            for name in spec.export_names():
                if name in result:
                    # Export name collision.
                    collisions.setdefault(name, set()).update({result[name], spec})
                else:
                    result[name] = spec
        Controller._check_export_collisions(collisions)
        return result

    @staticmethod
    def _init_service_specs(service_configs: Sequence[JSONType]) -> list[ServiceSpec]:
        # Attempt to create a ServiceSpec for each service.
        specs = []
        ControllerErrors.InitSpecs.collect_errors(
            service_configs,
            lambda c: specs.append(ServiceSpec(c)),
            ServiceControlError,
            key_fn=lambda c: c.get('$name', c.get('$class'))
        )
        return specs

    @staticmethod
    def _spec_to_deps(
        specs: Sequence[ServiceSpec], export_to_spec: Mapping[str, ServiceSpec]
    ) -> dict[ServiceSpec, set[ServiceSpec]]:
        # Gives a mapping from Service classes to the Service classes they depend on.
        result = {}
        unsatisfied = {}  # Keep track of all unsatisfied dependencies.
        for spec in specs:
            spec_deps = set()
            for dep in spec.dep_names():
                spec_dep = export_to_spec.get(dep)
                if not spec_dep:
                    unsatisfied.setdefault(spec, set()).add(dep)
                else:
                    spec_deps.add(spec_dep)
            result[spec] = spec_deps
        Controller._check_unsatisfied_deps(unsatisfied)
        return result

    @staticmethod
    def _validate(config: JSONType) -> None:
        # Validate top-level controller config. Service configs will be validated after their classes are imported.
        try:
            jsonschema.validate(config, Controller.SCHEMA)
        except ValidationError as e:
            raise ControllerErrors.SchemaValidation(config=config, error=e)

    def __init__(self, config: JSONType) -> None:
        """Initializes a controller with the application config.

        :param config: Config to initialize with.
        :raise ServiceControlError: If any of the following are true:
            * A circular dependency among services is detected.
            * Multiple services export an object of the same name.
            * One or more service specs fail to initialize.
            * Multiple services are configured to have the same name.
            * The top-level controller config failed validation.
            * One or more services have one or more unsatisfied dependencies.
        """
        # Perform default registration.
        registrar.register_defaults()

        self._validate(config)

        service_configs = config['services']
        service_specs = self._init_service_specs(service_configs)
        self._check_name_collisions(service_specs)
        export_to_spec = self._export_to_spec(service_specs)
        spec_to_deps = self._spec_to_deps(service_specs, export_to_spec)
        with ControllerErrors.CircularDependency.wrap(BRFuncErrors.CircularDependency):
            self.spec_stages = br.dag_stages(spec_to_deps)
        self.service_stages = []
        self.name_to_service = {}
        
    def job(self, _name: str, /, *args: str) -> None:
        """Attempts to run the job on the service with the given name with the given arguments.
        
        :param _name: Name of the service to run the job with.
        :param args: Arguments to pass to the job.
        :raise ServiceControlError: If no service with the given name could be found or if the job did not complete
            successfully.
        """
        # First positional argument is called '_name' in case a job takes a keyword argument called 'name'.
        service = self.service(_name)
        try:
            service.job(*args)
        except Exception as e:
            raise ControllerErrors.JobFailed(args=args, error=e, service=service)
        
    def purge(self, name: str) -> None:
        """Attempts to :meth:`purge <.Service.purge>` the service with the given name, resulting in that service's
        persistent data being deleted.
        
        :raise ServiceControlError: If the requested service could not be found or if the purge fails.
        """
        service = self.service(name)
        with ControllerErrors.PurgeFailed.wrap_error(Exception, service=service):
            service.purge()

    def service(self, name: str) -> Service:
        """Gets the :class:`.Service` with the given name.

        :param name: The name of the service to find.
        :return: The resulting service.
        :raise ServiceControlError: If no service exists with that name.
        """
        service = self.name_to_service.get(name)
        if service is None:
            raise ControllerErrors.NoSuchService(name=name)
        return service

    def start(self) -> None:
        """Attempts to :meth:`initialize <.Service.init>` and then  :meth:`start <.Service.start>` each service.

        :raise ServiceControlError: If one or more services fails to start.
        """
        # Mapping from exported names to the exported objects.
        name_to_object = {}
        for stage in self.spec_stages:
            services = set()
            for spec in stage:
                service = None
                try:
                    service = spec(name_to_object)
                    if not service.installed():
                        service.install()
                    service.start()
                    self.name_to_service[service.name] = service
                    services.add(service)
                except Exception as e1:
                    # Need to append these to stop already started services.
                    self.service_stages.append(services)
                    try:
                        self.stop()
                    except ControllerErrors.ServiceStop as e2:
                        raise ControllerErrors.ServiceStartStop(error=e1, errors=e2.errors, service=service, spec=spec)
                    raise ControllerErrors.ServiceStart(error=e1, service=service, spec=spec)
            self.service_stages.append(services)

    def stop(self) -> None:
        """Attempts to :meth:`stop <.Service.stop>` each service, resulting in each service, thus terminating the
        application.

        :raise: ControllerError: If one or more services fail to be stopped. All services will be tried in the reverse
            of the service dependency order regardless of errors.
        """
        failures = {}
        for stage in reversed(self.service_stages):
            for service in stage:
                try:
                    service.stop()
                except Exception as e:
                    failures[service] = e
        self.name_to_service.clear()
        self.service_stages.clear()
        if failures:
            raise ControllerErrors.ServiceStop(errors=failures)
