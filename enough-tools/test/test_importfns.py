import inspect
import logging
import re
import threading
from threading import Thread

import pytest

import enough as br
from enough.exceptions import BRImportErrors

import testpackage
import testpackage.testmodule as testmodule
from testpackage.testmodule import A, B, C


def test_checked_import() -> None:
    # Test that bobbeyreese.checked_import attempts to import an object from a fully-qualified name, but raises an
    # exception if the given predicate fails.
    assert br.checked_import('threading.Thread', lambda x: x.__name__ == 'Thread') is Thread
    with br.raises(BRImportErrors.CheckFailed(Thread)):
        br.checked_import('threading.Thread', lambda x: x.__name__ != 'Thread')


def test_import_object() -> None:
    # Test that we can import an object using its fully-qualified name using bobbeyreese.import_object(fqln).
    assert br.import_object('threading.Thread') is Thread
    assert br.import_object('re.compile') is re.compile

    # noinspection PyTypeChecker
    with pytest.raises(BRImportErrors.ModuleImport) as exc_info:
        br.import_object('THREADING.Thread')
    assert exc_info.value.name == 'THREADING'
    assert isinstance(exc_info.value.error, ModuleNotFoundError)

    with br.raises(BRImportErrors.ObjectNotFound(module=threading, name='Tread')):
        br.import_object('threading.Tread')


def test_module_members() -> None:
    # Test that bobbeyreese.module_members gets all the members of a module which satisfy a given predicate.
    assert set(br.module_members(testpackage.testmodule, inspect.isclass)) == {A, B, C}


def test_typed_import() -> None:
    # Test that bobbeyreese.typed_import attempts to import an object, but raises an exception if the imported object
    # is not of the specified type.
    assert br.typed_import('logging.INFO', int) == logging.INFO
    assert br.typed_import('threading.Thread', type) is Thread

    with br.raises(BRImportErrors.InstanceCheckFailed(obj=logging.INFO, type=type)):
        br.typed_import('logging.INFO', type)
    with br.raises(BRImportErrors.InstanceCheckFailed(obj=Thread, type=int)):
        br.typed_import('threading.Thread', int)


def test_typed_module_members() -> None:
    # Test that bobbeyreese.typed_module_members gets all members of a module which are of the given type.
    assert set(br.typed_module_members(testpackage.testmodule, type)) == {A, B, C}
    assert set(br.typed_module_members(testpackage.testmodule, int)) == {testmodule.a, testmodule.b}
