import unittest.mock as mock

import enough

import servicecontrol
import servicecontrol.core.registrar as registrar
from servicecontrol.core import Service
from servicecontrol.core.exceptions import RegistrationErrors

import testpackage
from testpackage.testmodule1 import B, C
from testpackage.sub.testmodule2 import D


def test_recursively_register() -> None:
    # Test that registrar.recursively_register iterates over all modules in a
    # package recursively and registers all services found.
    with mock.patch(
        'servicecontrol.core.registrar.register', autospec=True
    ) as mock_register:
        registrar.recursively_register(testpackage)
        mock_register.assert_has_calls(
            [mock.call('Base', B), mock.call('Case', C), mock.call('Dear', D)],
            any_order=True
        )


def test_register_and_find() -> None:
    # Test that register.register correctly registers a service so that it may
    # be found with registrar.find.

    # First try to register a class that isn't a service and expect an
    # exception.
    class NotAService: pass

    with enough.raises(RegistrationErrors.NotAService(cls=NotAService)):
        # noinspection PyTypeChecker
        registrar.register('NotService', NotAService)

    assert registrar.find('Base') is None
    registrar.register('Base', B)
    assert registrar.find('Base') == B
    assert registrar.find('base') == B

    # Try with an implicit service.
    class ImplicitService(Service):
        EXPORTS = {'a', 'b'}
        IMPLICIT = True

    registrar.register('implicit', ImplicitService)
    assert registrar.find('implicit') == ImplicitService
    assert registrar.find_implicit('a') == ImplicitService
    assert registrar.find_implicit('b') == ImplicitService
    assert registrar.find_implicit('c') is None

    # Try with another implicit service which has differently-named exports.
    class ImplicitService2(Service):
        EXPORTS = {'c', 'd'}
        IMPLICIT = True

    registrar.register('implicit2', ImplicitService2)
    assert registrar.find_implicit('b') == ImplicitService
    assert registrar.find_implicit('d') == ImplicitService2

    # Trying to register another implicit service which has some of the same
    # export names should fail.
    class ImplicitService3(Service):
        EXPORTS = {'a', 'd'}
        IMPLICIT = True

    with enough.raises(RegistrationErrors.ImplicitExists(
        exports={'a', 'd'}, service=ImplicitService3
    )):
        registrar.register('implicit3', ImplicitService3)

    # Trying to register another service with the same name should result in an
    # exception.
    with enough.raises(RegistrationErrors.RegistrationExists(
        attempted=C, name='base', registered=B
    )):
        registrar.register('base', C)


def test_register_defaults() -> None:
    # Test that registrar.register_defaults recursively registers are services
    # under the servicecontrol package.
    registrar._default_registration_done = False
    with mock.patch(
        'servicecontrol.core.registrar.recursively_register', autospec=True
    ) as mock_recurse:
        registrar.register_defaults()
        mock_recurse.assert_called_once_with(servicecontrol)
        assert registrar._default_registration_done


def test_register_all_in_module() -> None:
    # Test that registrar.register_all_in_module registers all services in that
    # module.
    with mock.patch(
        'servicecontrol.core.registrar.register', autospec=True
    ) as mock_register:
        # noinspection PyUnresolvedReferences
        registrar.register_all_in_module(testpackage.testmodule1)
        mock_register.assert_has_calls(
            [mock.call('Base', B), mock.call('Case', C)],
            any_order=True
        )
