from servicecontrol.tools.scheduler import SchedulerService


def test_service() -> None:
    # Just check that SchedulerService can be initialized from an empty config.
    SchedulerService({})
