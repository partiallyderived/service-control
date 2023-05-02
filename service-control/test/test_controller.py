import copy
import unittest.mock as mock
from typing import Final, MutableMapping
from unittest.mock import Mock

import enough
from enough import JSONType

from jsonschema import ValidationError

import pytest

from servicecontrol.core import Controller, Service, ServiceSpec
from servicecontrol.core.exceptions import ControllerErrors, ServiceErrors


# Service classes to use for testing.

class Service1(Service):
    EXPORTS: Final[frozenset[str]] = frozenset({'export1', 'export2'})
    NAME: Final[str] = 'Service1'
    SCHEMA: Final[JSONType] = {
        'type': 'object',
        'additionalProperties': False
    }

    # noinspection PyUnusedLocal
    def __init__(
        self,
        config: JSONType,
        export3: str,
        export4: str,
        export5: str,
        export8: str
    ) -> None:
        super().__init__(config)
        self.export1 = 1
        self.export2 = 2


class Service2(Service):
    EXPORTS: Final[frozenset[str]] = frozenset({'export3', 'export4'})
    NAME: Final[str] = 'Service2'
    SCHEMA: Final[JSONType] = {
        'type': 'object',
        'additionalProperties': False
    }

    # noinspection PyUnusedLocal
    def __init__(self, config: JSONType, export6: str) -> None:
        super().__init__(config)
        self.export3 = 3
        self.export4 = 4


class Service3(Service):
    EXPORTS: Final[frozenset[str]] = frozenset({'export5', 'export6'})
    NAME: Final[str] = 'Service3'
    SCHEMA: Final[JSONType] = {
        'type': 'object',
        'additionalProperties': False
    }

    # noinspection PyUnusedLocal
    def __init__(self, config: JSONType, export7: str) -> None:
        super().__init__(config)
        self.export5 = 5
        self.export6 = 6


class Service4(Service):
    EXPORTS: Final[frozenset[str]] = frozenset({'export7', 'export8'})
    NAME: Final[str] = 'Service4'

    def __init__(self, config: JSONType) -> None:
        super().__init__(config)
        self.export7 = 7
        self.export8 = 8


class Service5(Service):
    EXPORTS: Final[frozenset[str]] = frozenset({'export1', 'export6'})
    NAME: Final[str] = 'Service5'

    def __init__(self, config: JSONType) -> None:
        super().__init__(config)
        self.export1 = 1
        self.export6 = 6


@pytest.fixture
def controller_config() -> JSONType:
    # Controller config to use for testing.
    return {
        'services': [{
            '$class': Service1.cls_name()
        }, {
            '$class': Service2.cls_name()
        }, {
            '$class': Service3.cls_name()
        }, {
            '$class': Service4.cls_name()
        }]
    }


@pytest.fixture
def controller(controller_config: JSONType) -> Controller:
    # Controller to use for testing.
    return Controller(controller_config)


@pytest.fixture
def mock_services(controller: Controller) -> list[Mock]:
    # Mock services to use to ensure the correct methods were called in various
    # controller operations.
    mock1, mock2, mock3, mock4 = [
        Mock(spec=Service),
        Mock(spec=Service),
        Mock(spec=Service),
        Mock(spec=Service)
    ]
    services = [mock1, mock2, mock3, mock4]
    service_stages = []
    service_iter = iter(services)
    name_to_service = {}
    for stage in controller.spec_stages:
        service_stage = set()
        for spec in stage:
            nxt = next(service_iter)
            nxt.name = spec.name

            # Useful for determining which spec goes with which service.
            nxt._spec_ = spec
            service_stage.add(nxt)
            name_to_service[nxt.name] = nxt
        service_stages.append(services)

    controller.service_stages = service_stages
    controller.name_to_service = copy.copy(name_to_service)

    # noinspection PyUnusedLocal
    def mock_call(_spec: ServiceSpec, exports: MutableMapping) -> Mock:
        return name_to_service[_spec.name]

    with mock.patch.object(ServiceSpec, '__call__', new=mock_call):
        yield services


# Different specs to use for testing.
@pytest.fixture
def spec1() -> ServiceSpec:
    return ServiceSpec({'$class': Service1.cls_name()})


@pytest.fixture
def spec2() -> ServiceSpec:
    return ServiceSpec({'$class': Service2.cls_name()})


@pytest.fixture
def spec3() -> ServiceSpec:
    return ServiceSpec({'$class': Service3.cls_name()})


@pytest.fixture
def spec4() -> ServiceSpec:
    return ServiceSpec({'$class': Service4.cls_name()})


@pytest.fixture
def spec5() -> ServiceSpec:
    return ServiceSpec({'$class': Service5.cls_name()})


def test_check_export_collisions(
    spec1: ServiceSpec,
    spec2: ServiceSpec,
    spec3: ServiceSpec,
    spec4: ServiceSpec
) -> None:
    # Check that Controller._check_export_collisions correctly raises an
    # exception when export name collisions are detected.

    # No collisions, no exception.
    Controller._check_export_collisions({})

    collisions = {
        'export1': {spec1, spec2},
        'export2': {spec3, spec4}
    }
    with enough.raises(ControllerErrors.ExportCollision(collisions=collisions)):
        Controller._check_export_collisions(collisions)


def test_check_name_collisions(
    spec1: ServiceSpec,
    spec2: ServiceSpec,
    spec3: ServiceSpec,
    spec4: ServiceSpec
) -> None:
    # Check that Controller._check_name_collisions correctly determines when two
    # or more services share the same name.

    # No collisions with these specs.
    Controller._check_name_collisions([spec1, spec2, spec3, spec4])

    # Change names so that there are collisions.
    spec2.name = spec1.name
    spec4.name = spec3.name

    with enough.raises(ControllerErrors.NameCollision(collisions={
        spec1.name: {spec1, spec2},
        spec3.name: {spec3, spec4}
    })):
        Controller._check_name_collisions([spec1, spec2, spec3, spec4])


def test_check_unsatisfied_deps(spec1: ServiceSpec, spec2: ServiceSpec) -> None:
    # Check that Controller._check_unsatisfied_deps correctly raises an
    # exception when there are service dependencies that are unsatisfied.

    # No unsatisfied dependencies, no exception.
    Controller._check_unsatisfied_deps({})

    unsatisfied = {
        spec1: {'dep1', 'dep2'},
        spec2: {'dep3', 'dep4'}
    }
    with enough.raises(ControllerErrors.UnsatisfiedDependencies(
        unsatisfied=unsatisfied
    )):
        Controller._check_unsatisfied_deps(unsatisfied)


def test_export_to_spec(
    spec1: ServiceSpec,
    spec2: ServiceSpec,
    spec3: ServiceSpec,
    spec4: ServiceSpec,
    spec5: ServiceSpec
) -> None:
    # _check_export_collisions is already tested, so mock it.

    with mock.patch.object(
        Controller, '_check_export_collisions'
    ) as mock_check:
        assert Controller._export_to_spec([spec1, spec2, spec3, spec4]) == {
            'export1': spec1,
            'export2': spec1,
            'export3': spec2,
            'export4': spec2,
            'export5': spec3,
            'export6': spec3,
            'export7': spec4,
            'export8': spec4
        }
        mock_check.assert_called_with({})

        # Try with a conflict, make sure _check_export_collisions is called with
        # the correct arguments.
        Controller._export_to_spec([spec1, spec2, spec3, spec4, spec5])

        mock_check.assert_called_with({
            'export1': {spec1, spec5},
            'export6': {spec3, spec5}
        })


def test_init_service_specs() -> None:
    # Check that service specs are properly created from a sequence of service
    # configs.
    service_configs = [{
        '$class': Service1.cls_name()
    }, {
        '$class': Service2.cls_name()
    }, {
        '$class': Service3.cls_name()
    }, {
        '$class': Service4.cls_name()
    }]
    results = Controller._init_service_specs(copy.deepcopy(service_configs))
    assert results[0].cls == Service1
    assert results[1].cls == Service2
    assert results[2].cls == Service3
    assert results[3].cls == Service4

    # Test that failing to create some of the specs results in
    # ControllerErrors.InitSpecs being raised.
    service_configs[0]['fake_conf1'] = 'fake'
    service_configs[2]['fake_conf3'] = 'fake'

    # noinspection PyTypeChecker
    with pytest.raises(ControllerErrors.InitSpecs) as exc_info:
        Controller._init_service_specs(service_configs)
    assert exc_info.value.errors.keys() == {
        Service1.cls_name(), Service3.cls_name()
    }
    assert all(
        isinstance(e, ServiceErrors.SchemaValidation)
        for e in exc_info.value.errors.values()
    )


def test_spec_to_deps(
    spec1: ServiceSpec,
    spec2: ServiceSpec,
    spec3: ServiceSpec,
    spec4: ServiceSpec
) -> None:
    # Test that mapping of specs to dependencies is created correctly.

    # Controller._check_unsatisfied_deps is already tested, so mock it.
    with mock.patch.object(Controller, '_check_unsatisfied_deps') as mock_check:
        specs = [spec1, spec2, spec3, spec4]
        assert Controller._spec_to_deps(
            specs, Controller._export_to_spec(specs)
        ) == {
            spec1: {spec2, spec3, spec4},
            spec2: {spec3},
            spec3: {spec4},
            spec4: set()
        }
        mock_check.assert_called_with({})

        # Check that _check_unsatisfied_deps is called with the right arguments
        # when dependencies are unsatisfied.
        Controller._spec_to_deps(
            [spec1, spec2], Controller._export_to_spec([spec1, spec2])
        )
        mock_check.assert_called_with({
            spec1: {'export5', 'export8'},
            spec2: {'export6'}
        })


def test_validate() -> None:
    # Check that Controller._validate correctly raises a SchemaValidationError
    # when the config does not match the schema.

    # Should be no exception here.
    config = {'services': [{'$class': Service1.cls_name()}]}
    Controller._validate(config)

    # Use key 'service' instead of 'services' to get a validation error.
    config['service'] = config.pop('services')
    # noinspection PyTypeChecker
    with pytest.raises(ControllerErrors.SchemaValidation) as exc_info:
        Controller._validate(config)
    assert isinstance(exc_info.value.error, ValidationError)
    assert exc_info.value.config == config


def test_init(controller_config: JSONType) -> None:
    # Test Controller.__init__.

    # Mock Controller._validate so we can see if it was called.
    with mock.patch.object(
        Controller, '_validate', autospec=True
    ) as mock_validate:
        controller = Controller(controller_config)
        mock_validate.assert_called_with(controller_config)

        # Check service execution order.
        service_classes = [
            {spec.cls for spec in stage} for stage in controller.spec_stages
        ]
        assert service_classes == [
            {Service4}, {Service3}, {Service2}, {Service1}
        ]


def test_job(controller: Controller, mock_services: list[Mock]) -> None:
    # Test cases for Controller.job.

    # Try without exception.
    controller.job(mock_services[0].name, 'arg 1', 'arg 2')
    mock_services[0].job.assert_called_with('arg 1', 'arg 2')

    # Try for service which cannot be found.
    with enough.raises(ControllerErrors.NoSuchService(name='Not a Service')):
        controller.job('Not a Service')

    # Try with a job that fails.
    err = ValueError()
    mock_services[1].job.side_effect = err
    with enough.raises(ControllerErrors.JobFailed(
        args=('arg 1', 'arg 2'), error=err, service=mock_services[1])
    ):
        controller.job(mock_services[1].name, 'arg 1', 'arg 2')


def test_purge(controller: Controller, mock_services: list[Mock]) -> None:
    # Test cases for Controller.purge.

    # First try without exception.
    controller.purge(mock_services[0].name)
    mock_services[0].purge.assert_called_with()
    mock_services[1].purge.assert_not_called()
    mock_services[2].purge.assert_not_called()
    mock_services[3].purge.assert_not_called()

    # Try with service that cannot be found.
    with enough.raises(ControllerErrors.NoSuchService(name='Not a Service')):
        controller.purge('Not a Service')

    # Try with a purge failure.
    err = ValueError()
    mock_services[1].purge.side_effect = err
    with enough.raises(ControllerErrors.PurgeFailed(
        error=err, service=mock_services[1]
    )):
        controller.purge(mock_services[1].name)


def test_service(controller: Controller, mock_services: list[Mock]) -> None:
    # Test that Controller.service can get a service by it's name.
    assert controller.service(mock_services[0].name) == mock_services[0]
    assert controller.service(mock_services[2].name) == mock_services[2]

    # If the service does not exist, a NoSuchServiceError is raised.
    with enough.raises(ControllerErrors.NoSuchService(name='does not exist')):
        controller.service('does not exist')


def test_start(controller: Controller, mock_services: list[Mock]) -> None:
    # Have only services 0 and 3 require installation.
    mock_services[0].installed.return_value = False
    mock_services[1].installed.return_value = True
    mock_services[2].installed.return_value = True
    mock_services[3].installed.return_value = False

    controller.name_to_service.clear()
    controller.start()
    assert controller.name_to_service == {
        mock_services[0].name: mock_services[0],
        mock_services[1].name: mock_services[1],
        mock_services[2].name: mock_services[2],
        mock_services[3].name: mock_services[3]
    }

    # Make sure install methods were only called when service.installed() is
    # False.
    mock_services[0].install.assert_called()
    mock_services[1].install.assert_not_called()
    mock_services[2].install.assert_not_called()
    mock_services[3].install.assert_called()

    # Make sure ALL start methods were called.
    [m.start.assert_called() for m in mock_services]

    # Reset start mocks.
    [m.start.reset_mock() for m in mock_services]

    # Raise an exception when trying to start service at index 2. Ensure that
    # controller.stop is called.
    with mock.patch.object(controller, 'stop', autospec=True) as mock_stop:
        err = ValueError()
        mock_services[2].start.side_effect = err
        controller.name_to_service.clear()
        with enough.raises(ControllerErrors.ServiceStart(
            error=err, service=mock_services[2], spec=mock_services[2]._spec_
        )):
            controller.start()

        mock_services[0].start.assert_called()
        mock_services[1].start.assert_called()
        mock_services[2].start.assert_called()
        mock_services[3].start.assert_not_called()
        mock_stop.assert_called()
        controller.name_to_service.clear()

        # Same test, but also have controller.stop raise a ServiceStopError.
        # Need to mock traceback.format_exception to suppress some exception
        # behaviors.
        with mock.patch('traceback.format_exception'):
            err1 = ValueError()
            err2 = TypeError()
            stop_err = ControllerErrors.ServiceStop(errors={
                mock_services[0]: err1,
                mock_services[1]: err2
            })
            mock_stop.side_effect = stop_err
            with enough.raises(ControllerErrors.ServiceStartStop(
                error=err,
                errors=stop_err.errors,
                service=mock_services[2],
                spec=mock_services[2]._spec_
            )):
                controller.start()
            controller.name_to_service.clear()

        # Now try scenario where a service fails to be created.
        mock_stop.side_effect = None
        mock_spec = Mock(spec=ServiceSpec)
        mock_spec.name = 'Arbitrary'
        controller.spec_stages[0] = {mock_spec}
        mock_spec.side_effect = err
        with enough.raises(ControllerErrors.ServiceStart(
            error=err, service=None, spec=mock_spec)
        ):
            controller.start()


def test_stop(controller: Controller, mock_services: list[Mock]) -> None:
    # Test that controller.stop calls all service stop methods, and test
    # exceptional cases.

    # Need a copy of these to reassign after the originals are cleared.
    name_to_service_copy = copy.copy(controller.name_to_service)
    service_stages_copy = copy.copy(controller.service_stages)

    # No exceptions first.
    controller.stop()
    [m.stop.assert_called() for m in mock_services]
    assert not controller.name_to_service
    assert not controller.service_stages
    controller.name_to_service = name_to_service_copy
    controller.service_stages = service_stages_copy
    [m.stop.reset_mock() for m in mock_services]

    # Now try with 2 exceptions.
    err1 = ValueError()
    err2 = TypeError()
    mock_services[0].stop.side_effect = err1
    mock_services[2].stop.side_effect = err2

    with enough.raises(ControllerErrors.ServiceStop(errors={
        mock_services[0]: err1,
        mock_services[2]: err2
    })):
        controller.stop()
