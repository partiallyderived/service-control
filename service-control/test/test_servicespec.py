import unittest.mock as mock
from threading import Thread
from typing import Final

import enough
from enough import JSONType
from enough.exceptions import EnoughError

import pytest

import servicecontrol.core.registrar as registrar
from servicecontrol.core import Service, ServiceSpec
from servicecontrol.core.exceptions import ServiceSpecErrors


class SomeService(Service):
    EXPORTS: Final[frozenset[str]] = frozenset(
        {'export1', 'export2', 'export3'}
    )
    NAME: Final[str] = 'SomeService'
    SCHEMA: Final[JSONType] = {
        'type': 'object',
        'properties': {
            'conf1': {'type': 'string'},
            'conf2': {'type': 'string'}
        }
    }

    def __init__(
        self, config: JSONType, dep1: str, dep2: str, dep3: str
    ) -> None:
        super().__init__(config)
        self.dep1 = dep1
        self.dep2 = dep2
        self.dep3 = dep3
        self.export1 = 1
        self.export2 = 2
        self.export3 = 3


class OtherService1(Service):
    NAME: Final[str] = 'TestName'


class OtherService2(Service):
    NAME: Final[str] = 'TestName'


class NoNameService(Service): pass


@pytest.fixture
def service_config() -> JSONType:
    return {
        '$class': SomeService.cls_name(),
        '$dep-overrides': {
            'dep1': 'dep1_override'
        },
        '$export-overrides': {
            'export2': 'export2_override',
            'export3': 'export3_override'
        },
        'conf1': 'value1',
        'conf2': 'value2'
    }


@pytest.fixture
def spec(service_config: JSONType) -> ServiceSpec:
    return ServiceSpec(service_config)


def test_check_unrecognized(spec: ServiceSpec) -> None:
    # Check that ServiceSpec._check_unrecognized correctly raises an exception
    # when unrecognized overrides for dependencies or exports are specified.

    # Check passes when the second argument (overrides) is a subset of the first
    # argument (recognized).
    spec._check_unrecognized(set(), set(), ServiceSpecErrors.NoSuchDependency)
    spec._check_unrecognized(set(), set(), ServiceSpecErrors.NoSuchExport)
    spec._check_unrecognized(
        {'arg1', 'arg2'}, set(), ServiceSpecErrors.NoSuchDependency
    )
    spec._check_unrecognized(
        {'arg1', 'arg2'}, {'arg1'}, ServiceSpecErrors.NoSuchExport
    )
    spec._check_unrecognized(
        {'arg1', 'arg2'}, {'arg1', 'arg2'}, ServiceSpecErrors.NoSuchDependency
    )

    # Otherwise, check should fail, raising the given exception and formatting
    # the exception message using the given string.
    with enough.raises(ServiceSpecErrors.NoSuchExport(
        config=spec.config, names={'arg1'}, service=spec.cls
    )):
        spec._check_unrecognized(
            set(), {'arg1'}, ServiceSpecErrors.NoSuchExport
        )

    with enough.raises(ServiceSpecErrors.NoSuchDependency(
        config=spec.config, names={'arg2', 'arg3'}, service=spec.cls)
    ):
        spec._check_unrecognized(
            {'arg1'}, {'arg1', 'arg2', 'arg3'},
            ServiceSpecErrors.NoSuchDependency
        )


def test_resolve_class_and_name(spec: ServiceSpec) -> None:
    # Test that ServiceSpec._resolve_class_and_name correctly infers a service's
    # name and class from configured values or else raises an exception.

    # Both class and name specified.
    spec._resolve_class_and_name(OtherService1.cls_name(), 'SomeName')
    assert spec.cls == OtherService1
    assert spec.name == 'SomeName'

    # Only class specified.
    spec._resolve_class_and_name(OtherService1.cls_name(), None)
    assert spec.cls == OtherService1
    assert spec.name == 'TestName'

    # Only class with no default name should result in exception.
    with enough.raises(ServiceSpecErrors.MissingName(
        config=spec.config, service=NoNameService
    )):
        spec._resolve_class_and_name(NoNameService.cls_name(), None)

    # Non-existent class should result in ServiceSpecErrors.ServiceImport.
    # noinspection PyTypeChecker
    with pytest.raises(ServiceSpecErrors.ServiceImport) as exc_info:
        spec._resolve_class_and_name('does.not.exist', None)
    assert exc_info.value.name == 'does.not.exist'
    assert isinstance(exc_info.value.error, EnoughError)

    # Only name specified, no registration.
    with enough.raises(ServiceSpecErrors.NoSuchService(name='TestName')):
        spec._resolve_class_and_name(None, 'TestName')

    # Only name specified, service registered by that name.
    registrar.register('TestName', OtherService1)
    spec._resolve_class_and_name(None, 'TestName')
    assert spec.cls == OtherService1
    assert spec.name == 'TestName'

    # Neither class or name specified.
    with enough.raises(ServiceSpecErrors.MissingClass(config=spec.config)):
        spec._resolve_class_and_name(None, None)


def test_validate(spec: ServiceSpec) -> None:
    # Test the ServiceSpec._validate correctly calls both Service.check_init()
    # and Service.validate().

    with mock.patch.multiple(
        spec.cls, check_init=mock.DEFAULT, validate=mock.DEFAULT, autospec=True
    ) as mocks:
        spec._validate({})
        mocks['check_init'].assert_called()
        mocks['validate'].assert_called()


def test_dep_names(spec: ServiceSpec) -> None:
    # Check that dependency names are returned by ServiceSpec.dep_names().
    assert spec.dep_names() == {'dep1_override', 'dep2', 'dep3'}


def test_export_names(spec: ServiceSpec) -> None:
    # Check that export names are returned by ServiceSpec.export_names().
    assert spec.export_names() == {
        'export1', 'export2_override', 'export3_override'
    }


def test_call(spec: ServiceSpec) -> None:
    # It is the responsibility of the Controller to check that spec is called
    # with the correct arguments.
    # Thus, just test that a successful call behaves correctly.

    exports = {
        'dep1_override': 'one',
        'dep2': 'two',
        'dep3': 'three',
        'extra1': 'extra_one',
        'extra2': 'extra_two',
        'extra3': 'extra_three'
    }
    service = spec(exports)
    assert isinstance(service, SomeService)
    assert service.dep1 == 'one'
    assert service.dep2 == 'two'
    assert service.dep3 == 'three'

    # New exports should be added.
    assert exports == {
        'dep1_override': 'one',
        'dep2': 'two',
        'dep3': 'three',
        'extra1': 'extra_one',
        'extra2': 'extra_two',
        'extra3': 'extra_three',
        'export1': 1,
        'export2_override': 2,
        'export3_override': 3
    }


def test_init(service_config: JSONType) -> None:
    # Check that ServiceSpec.__init__ behaves correctly.

    # Test that a configuration for a class which is not a service results in a
    # NotAServiceError.
    with enough.raises(ServiceSpecErrors.NotAService(cls=Thread)):
        ServiceSpec({'$class': 'threading.Thread', '$name': 'Thread'})

    # Now try to successfully create a ServiceSpec.
    # Just mock _check_unrecognized and _validate since they are already tested.
    with mock.patch.multiple(
        ServiceSpec,
        _check_unrecognized=mock.DEFAULT,
        _validate=mock.DEFAULT,
        autospec=True
    ) as mocks:
        spec = ServiceSpec(service_config)

        mocks['_check_unrecognized'].assert_any_call(
            spec,
            {'dep1', 'dep2', 'dep3'},
            {'dep1'},
            ServiceSpecErrors.NoSuchDependency
        )
        mocks['_check_unrecognized'].assert_any_call(
            spec,
            {'export1', 'export2', 'export3'},
            {'export2', 'export3'},
            ServiceSpecErrors.NoSuchExport
        )

        mocks['_validate'].assert_called_with(spec, {
            'conf1': 'value1',
            'conf2': 'value2'
        })

    # 'Meta' keys should be popped.
    assert spec.config == {
        'conf1': 'value1',
        'conf2': 'value2'
    }

    assert spec.dep_overrides == {
        'dep1': 'dep1_override'
    }

    assert spec.export_overrides == {
        'export2': 'export2_override',
        'export3': 'export3_override'
    }
