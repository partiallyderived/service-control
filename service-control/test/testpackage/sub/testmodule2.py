from typing import ClassVar

from servicecontrol.core import Service


class D(Service):
    NAME: ClassVar[str] = 'Dear'


class E:
    NAME: ClassVar[str] = 'Ear'


class F:
    NAME: ClassVar[str] = 'Fear'
