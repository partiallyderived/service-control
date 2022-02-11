import sched
from typing import Final

from enough import JSONType
from servicecontrol.core import Service


class SchedulerService(Service):
    EXPORTS: Final[frozenset[str]] = frozenset({'scheduler'})
    IMPLICIT: Final[bool] = True
    NAME: Final[str] = 'scheduler'
    SCHEMA: Final[JSONType] = {
        'description': 'Configuration for SchedulerService.',
        'type': 'object',
        'additionalProperties': False
    }

    #: Exported scheduler.
    scheduler: sched.scheduler

    def __init__(self, config: JSONType) -> None:
        """Initializes this service with the given config.

        :param config: Config to initialize with.
        """
        super().__init__(config)
        self.scheduler = sched.scheduler()
