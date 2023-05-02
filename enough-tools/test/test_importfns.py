import inspect
import logging
import re
import threading
from threading import Thread

import pytest

import enough
from enough.exceptions import EnoughImportsErrors

import testpackage
import testpackage.testmodule as testmodule
from testpackage.testmodule import A, B, C


def test_checked_import() -> None:
    # Test that checked_import attempts to import an object from a
    # fully-qualified name, but raises an exception if the given predicate
    # fails.
    assert enough.checked_import(
        'threading.Thread', lambda x: x.__name__ == 'Thread'
    ) is Thread
    with enough.raises(EnoughImportsErrors.CheckFailed(Thread)):
        enough.checked_import(
            'threading.Thread', lambda x: x.__name__ != 'Thread'
        )


def test_import_object() -> None:
    # Test that we can import an object using its fully-qualified name using
    # import_object(fqln).
    assert enough.import_object('threading.Thread') is Thread
    assert enough.import_object('re.compile') is re.compile

    # noinspection PyTypeChecker
    with pytest.raises(EnoughImportsErrors.ModuleImport) as exc_info:
        enough.import_object('THREADING.Thread')
    assert exc_info.value.name == 'THREADING'
    assert isinstance(exc_info.value.error, ModuleNotFoundError)

    with enough.raises(
        EnoughImportsErrors.ObjectNotFound(module=threading, name='Tread')
    ):
        enough.import_object('threading.Tread')


def test_module_members() -> None:
    # Test module_members gets all the members of a module which satisfy a given
    # predicate.
    assert set(
        enough.module_members(testpackage.testmodule, inspect.isclass)
    ) == {A, B, C}


def test_typed_import() -> None:
    # Test that typed_import attempts to import an object, but raises an
    # exception if the imported object is not of the specified type.
    assert enough.typed_import('logging.INFO', int) == logging.INFO
    assert enough.typed_import('threading.Thread', type) is Thread

    with enough.raises(
        EnoughImportsErrors.InstanceCheckFailed(obj=logging.INFO, type=type)
    ):
        enough.typed_import('logging.INFO', type)
    with enough.raises(
        EnoughImportsErrors.InstanceCheckFailed(obj=Thread, type=int)
    ):
        enough.typed_import('threading.Thread', int)


def test_typed_module_members() -> None:
    # Test that typed_module_members gets all members of a module which are of
    # the given type.
    assert set(
        enough.typed_module_members(testpackage.testmodule, type)
    ) == {A, B, C}
    assert set(
        enough.typed_module_members(testpackage.testmodule, int)
    ) == {testmodule.a, testmodule.b}
