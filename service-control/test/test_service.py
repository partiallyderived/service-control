from typing import Final

import enough
from enough import JSONType

from jsonschema import ValidationError

import pytest

from servicecontrol.core import Service
from servicecontrol.core.exceptions import ServiceErrors


def test_check_init() -> None:
    # Test that a service whose first positional argument to __init__ is not
    # named "config" results in a NoConfigArgError being raised.

    class DefaultService(Service):
        # No override should be allowed.
        pass

    class ValidService1(Service):
        def __init__(self, config: JSONType) -> None:
            super().__init__(config)

    class ValidService2(Service):
        # noinspection PyUnusedLocal
        def __init__(self, config: JSONType, arg1: str, arg2: int) -> None:
            super().__init__(config)

    class NoConfigService(Service):
        # noinspection PyUnusedLocal
        def __init__(self, arg1: str, arg2: int) -> None:
            super().__init__({})

    class ConfigAsSecondArgumentService(Service):
        # noinspection PyUnusedLocal
        def __init__(self, arg: str, config: JSONType) -> None:
            super().__init__(config)

    class ConfigAsKeywordService(Service):
        def __init__(self, *, config: JSONType) -> None:
            super().__init__(config)

    DefaultService.check_init()
    ValidService1.check_init()
    ValidService2.check_init()

    with enough.raises(ServiceErrors.NoConfigArg(service=NoConfigService)):
        NoConfigService.check_init()

    with enough.raises(ServiceErrors.NoConfigArg(
        service=ConfigAsSecondArgumentService
    )):
        ConfigAsSecondArgumentService.check_init()

    with enough.raises(ServiceErrors.NoConfigArg(
        service=ConfigAsKeywordService
    )):
        ConfigAsKeywordService.check_init()


def test_default_name() -> None:
    # Test that the service default name is correctly inferred from NAME class
    # variable.
    class NoNameService(Service):
        NAME: None = None

    class NameService(Service):
        NAME: Final[str] = 'test-name'

    assert NoNameService.default_name() is None
    assert NameService.default_name() == 'test-name'


def test_dep_names() -> None:
    # Test that dependency names are correctly inferred from __init__ signature.
    class NoDeps(Service): pass

    class PositionalDeps(Service):
        # noinspection PyUnusedLocal
        def __init__(self, config: JSONType, dep1: str, dep2: str) -> None:
            super().__init__(config)

    class KeywordDeps(Service):
        # noinspection PyUnusedLocal
        def __init__(self, config: JSONType, *, dep1: str, dep2: str) -> None:
            super().__init__(config)

    class MixedDeps(Service):
        # noinspection PyUnusedLocal
        def __init__(
            self, config: JSONType, dep1: str, *, dep2: str, dep3: str
        ) -> None:
            super().__init__(config)

    assert NoDeps.dep_names() == set()
    assert PositionalDeps.dep_names() == {'dep1', 'dep2'}
    assert KeywordDeps.dep_names() == {'dep1', 'dep2'}
    assert MixedDeps.dep_names() == {'dep1', 'dep2', 'dep3'}


def test_export_names() -> None:
    # Test that export names are correctly inferred from EXPORTS class variable.
    class NoExportService(Service):
        EXPORTS: Final[frozenset] = frozenset()

    class SetExportService(Service):
        EXPORTS: Final[frozenset[str]] = frozenset({'export1', 'export2'})

    assert NoExportService.export_names() == set()
    assert SetExportService.export_names() == {'export1', 'export2'}


def test_installed_true_by_default() -> None:
    class SomeService(Service): pass

    # is True just to assert that it's actually True and not some other truthy
    # value.
    assert SomeService({}).installed() is True


def test_job_exception_by_default() -> None:
    # Test that Service.job raises an exception by default.
    class SomeService(Service): pass

    service = SomeService({})
    with enough.raises(ServiceErrors.NoJobsImplemented(service=service)):
        service.job()


def test_schema() -> None:
    # Test that a service's schema is correctly inferred from the SCHEMA class
    # variable.

    class NoSchemaService(Service): pass

    class SchemaService(Service):
        SCHEMA: Final[JSONType] = {
            'type': 'object',
            'properties': {
                'prop1': {'type': 'string'},
                'prop2': {'type': 'int'}
            }
        }

    assert NoSchemaService.schema() == {}
    assert SchemaService.schema() == SchemaService.SCHEMA


def test_validate() -> None:
    # Test that config validation raises a ServiceValidationError for an invalid
    # config.
    class SchemaService(Service):
        SCHEMA: Final[JSONType] = {
            'type': 'object',
            'properties': {
                'prop1': {
                    'type': 'string'
                },
                'prop2': {
                    'type': 'integer'
                }
            },
            'additionalProperties': False
        }

    # Valid configuration.
    SchemaService.validate({
        'prop1': 'value',
        'prop2': 6023
    })

    # noinspection PyTypeChecker
    with pytest.raises(ServiceErrors.SchemaValidation) as exc_info:
        SchemaService.validate({'prop3': 3})
    assert exc_info.value.config == {'prop3': 3}
    assert isinstance(exc_info.value.error, ValidationError)
