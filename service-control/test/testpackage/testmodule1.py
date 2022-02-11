# This file is used by test_util and test_registrar.

# Use this import to verify Thread is not included in module classes.
# noinspection PyUnresolvedReferences
from threading import Thread
from typing import ClassVar

from servicecontrol.core import Service

# Create some classes to load, some of which are services.


class A:
    NAME: ClassVar[str] = 'Ace'


class B(Service):
    NAME: ClassVar[str] = 'Base'


class C(Service):
    NAME: ClassVar[str] = 'Case'
