# This file is used by test_util and test_registrar.

# Use this import to verify Thread is not included in module classes.
# noinspection PyUnresolvedReferences
from threading import Thread

# Create some classes to load, some of which are services.


class A: pass
class B: pass
class C: pass


a = 20
b = 15
c = 10.0
