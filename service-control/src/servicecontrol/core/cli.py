import json
import os
import signal
import sys
import time
import traceback
from argparse import Action, ArgumentParser, Namespace
from collections.abc import Sequence
from typing import Final, TypeVar

from enough import EnumErrors

from servicecontrol.core._exception import ServiceControlError
from servicecontrol.core.controller import Controller


class CLIErrors(EnumErrors[ServiceControlError]):
    """Exception types raised in servicecontrol.core.cli."""
    ArgParse = 'Command line arguments are malformed.'
    ControllerInit = 'Failed to initialize controller: {_error_tb}', 'error'
    JobNoSuchService = 'No service is configured with the name "{name}"', 'name'
    NotAFile = '{name} is not a file.', 'name', FileNotFoundError
    PurgesFailed = (
        'Failed to purge the following services:\n\n'
            ''
            '{_fmt_error_map(lambda service: service.name)}',
        'errors'
    )
    PurgeNoSuchService = (
        'Aborting because no services are configured with these names: {", ".join(not_found)}',
        'not_found'
    )


A = TypeVar('A', bound=Action)

parser: Final[ArgumentParser] = ArgumentParser(description='Perform an action with a service controller.')
subparsers: Final[A] = parser.add_subparsers(dest='command')

start_parser: Final[A] = subparsers.add_parser('start')
start_parser.add_argument('config', help='Configuration to start with.')

job_parser: Final[A] = subparsers.add_parser('job')
job_parser.add_argument('config', help='Configuration to use to launch services to run job on.')
job_parser.add_argument('service', help='Name of service to run job with.')
job_parser.add_argument('args', nargs='*', help='Arguments to pass to the job.')

purge_parser: Final[A] = subparsers.add_parser('purge')
purge_parser.add_argument('config', help='Configuration to purge services with.')
purge_parser.add_argument('services', nargs='+', help='Names of services to purge.')


def _controller(parsed: Namespace) -> Controller:
    # Attempts to initialize a controller and raises an exception otherwise.
    with CLIErrors.ControllerInit.wrap_error(ServiceControlError):
        return Controller(parsed.config)


def _service_names(controller: Controller) -> set[str]:
    # Helper function to get all services names from a controller that hasn't started yet.
    return {spec.name for stage in controller.spec_stages for spec in stage}


def job(parsed: Namespace) -> None:
    """Handles running jobs with the controller using the parsed command line arguments.

    :param parsed: Parsed command line arguments.
    :raise ServiceControlError: If an error occurred when trying to initialize the controller or if the service for
        which the job was requested to be run on could not be found.
    """
    controller = _controller(parsed)
    service = parsed.service
    args = parsed.args
    all_names = _service_names(controller)
    if service not in all_names:
        raise CLIErrors.JobNoSuchService(name=service)
    controller.start()
    controller.job(service, *args)


def purge(parsed: Namespace) -> None:
    """Handle purging services with the controller using the parsed command line arguments.

    :param parsed: The parsed command line arguments.
    :raise ServiceControlError: If any of the following are true:
        * An error occurred when trying to initialize the controller.
        * Any services requested to be purged cannot not be found.
        * If one or more services fail to be purged.
    """
    services_to_purge = set(parsed.services)
    controller = _controller(parsed)
    all_names = _service_names(controller)
    not_found = services_to_purge - all_names
    if not_found:
        raise CLIErrors.PurgeNoSuchService(not_found=not_found)
    controller.start()
    failures = {}
    successes = set()

    for service in services_to_purge:
        try:
            controller.purge(service)
            successes.add(service)
        except Exception as e:
            failures[controller.name_to_service[service]] = e
    if successes:
        print(f'Successfully purged the following services: {", ".join(successes)}')
    else:
        print('No services successfully purged.', file=sys.stderr)
    if failures:
        raise CLIErrors.PurgesFailed(errors=failures)


def start(parsed: Namespace) -> None:
    """Handles starting the controller using the parsed command line arguments.

    :param parsed: The parsed command line arguments.
    :raise ServiceControlError: If there is an error when trying to initializing the controller.
    """
    controller = _controller(parsed)

    got_sigterm = False

    def handle_sigterm() -> None:
        nonlocal got_sigterm
        got_sigterm = True

    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    controller.start()

    print('Controller started successfully.')
    while not got_sigterm:
        time.sleep(0.1)

    controller.stop()


def main(args: Sequence[str]) -> None:
    """Handles command lines arguments and performs actions with a service controller accordingly.

    :param args: Command line arguments.
    :raise ServiceControlError: If any of the following are true:
        * The given config file could not be found or is not a file.
        * The arguments fail to be parsed
        * An error occurs in the course of trying to complete the requested task.
    """
    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        raise CLIErrors.ArgParse()
    if parsed.config is not None:
        if not os.path.isfile(parsed.config):
            raise CLIErrors.NotAFile(name=parsed.config)
        with open(parsed.config) as f:
            # For convenience, go ahead and load the config here.
            parsed.config = json.load(f)
    if parsed.command == 'job':
        job(parsed)
    elif parsed.command == 'purge':
        purge(parsed)
    elif parsed.command == 'start':
        start(parsed)
    else:
        raise AssertionError(f'Unexpected command: {parsed.command}')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception:
        traceback.print_exc()
        print('service-control failed.', file=sys.stderr)
        sys.exit(1)
