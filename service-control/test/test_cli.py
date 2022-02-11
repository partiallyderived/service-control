import copy
import json
import signal
import time
import unittest.mock as mock
from argparse import Namespace
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Final
from unittest.mock import Mock

import enough as br
import pytest
from enough import JSONType

import servicecontrol.core.cli as cli
from servicecontrol.core import Service
from servicecontrol.core.exceptions import CLIErrors, ControllerErrors


class Service1(Service):
    NAME: Final[str] = 'Service1'


class Service2(Service):
    NAME: Final[str] = 'Service2'


@pytest.fixture
def config() -> JSONType:
    return {
        'services': [{
            '$class': Service1.cls_name()
        }, {
            '$class': Service2.cls_name()
        }]
    }


@pytest.fixture
def mock_parsed(config: JSONType) -> Mock:
    mock_parsed = Mock(spec=Namespace)
    # As config is modified when loading service specs, this should be a copy of the config.
    mock_parsed.config = copy.deepcopy(config)
    return mock_parsed


def test_controller(mock_parsed: Mock) -> None:
    # Test that _controller correctly raises a CLIError is the controller fails to initialize.
    with mock.patch.object(cli.Controller, '__init__', autospec=True) as mock_init:
        err = ControllerErrors.NoSuchService(name='asdf')
        mock_init.side_effect = err
        with br.raises(CLIErrors.ControllerInit(error=err)):
            cli._controller(mock_parsed)


def test_main(config: JSONType) -> None:
    # Test that main calls the correct methods.
    with NamedTemporaryFile('w') as config_file:
        json.dump(config, config_file)
        config_file.flush()
        with mock.patch.multiple(
            'servicecontrol.core.cli', job=mock.DEFAULT, purge=mock.DEFAULT, start=mock.DEFAULT, autospec=True
        ) as mocks:
            mock_job = mocks['job']
            mock_purge = mocks['purge']
            mock_start = mocks['start']
            cli.main(['start', config_file.name])
            mock_start.assert_called_with(Namespace(command='start', config=config))

            # Without service, job should fail.
            with br.raises(CLIErrors.ArgParse()):
                cli.main(['job', config_file.name])

            cli.main(['job', config_file.name, 'SomeService'])
            mock_job.assert_called_with(Namespace(command='job', config=config, service='SomeService', args=[]))

            # Specify a non-existent config file.
            not_a_file = 'This is surely not a file.'
            with br.raises(CLIErrors.NotAFile(name=not_a_file)):
                cli.main(['job', not_a_file, 'SomeService'])

            cli.main(['job', config_file.name, 'SomeService', 'a', 'b', 'c'])
            mock_job.assert_called_with(
                Namespace(command='job', config=config, service='SomeService', args=['a', 'b', 'c'])
            )

            cli.main(['purge', config_file.name, Service1.default_name(), Service2.default_name()])
            mock_purge.assert_called_with(
                Namespace(command='purge', config=config, services=[Service1.default_name(), Service2.default_name()])
            )
            with br.raises(CLIErrors.ArgParse()):
                # Need at least one service.
                cli.main(['purge', config_file.name])

            # Just one service is okay.
            cli.main(['purge', config_file.name, Service1.default_name()])
            mock_purge.assert_called_with(
                Namespace(command='purge', config=config, services=[Service1.default_name()])
            )

            # Unrecognized command should raise an error.
            with br.raises(CLIErrors.ArgParse()):
                cli.main(['strap', config_file.name])


def test_job(config: JSONType, mock_parsed: Mock) -> None:
    # Test that the logic for running a job from command line arguments is correct.
    mock_parsed.service = Service1.default_name()
    mock_parsed.config = copy.deepcopy(config)

    # Run a job, see if it's called with the correct arguments.
    with mock.patch.object(Service1, 'job', autospec=True) as mock_job:
        mock_parsed.args = ['A', 'B']
        cli.job(mock_parsed)
        assert mock_job.call_args.args[1:] == ('A', 'B')

    mock_parsed.config = copy.deepcopy(config)

    # Try to run a job on an unrecognized service.
    mock_parsed.service = 'does-not-exist'
    with br.raises(CLIErrors.JobNoSuchService(name='does-not-exist')):
        cli.job(mock_parsed)


def test_purge(config: JSONType, mock_parsed: Mock) -> None:
    # Test that the logic for purging specified controller services from parsed command line arguments is correct.
    with mock.patch.object(Service1, 'purge', autospec=True) as mock_purge1:
        with mock.patch.object(Service2, 'purge', autospec=True) as mock_purge2:
            mock_parsed.services = [Service1.default_name(), Service2.default_name()]
            cli.purge(mock_parsed)
            mock_purge1.assert_called()
            mock_purge2.assert_called()
            mock_purge1.reset_mock()
            mock_purge2.reset_mock()
            # Reset the config.
            mock_parsed.config = copy.deepcopy(config)

            mock_parsed.services = [Service2.default_name()]
            cli.purge(mock_parsed)
            mock_purge1.assert_not_called()
            mock_purge2.assert_called()
            mock_purge2.reset_mock()
            mock_parsed.config = copy.deepcopy(config)

            # Try to purge non-existent service.
            mock_parsed.services = ['does-not-exist', Service2.default_name()]
            with br.raises(CLIErrors.PurgeNoSuchService(not_found={'does-not-exist'})):
                cli.purge(mock_parsed)
            mock_parsed.config = copy.deepcopy(config)

            # Even if both purges raise an exception, both purges should still end up being called.
            mock_parsed.services = [Service1.default_name(), Service2.default_name()]
            err1 = ValueError()
            err2 = TypeError()
            mock_purge1.side_effect = err1
            mock_purge2.side_effect = err2

            # noinspection PyTypeChecker
            with pytest.raises(CLIErrors.PurgesFailed) as exc_info:
                cli.purge(mock_parsed)
            errors = exc_info.value.errors
            assert len(errors) == 2
            for service, error in errors.items():
                if isinstance(service, Service1):
                    expected = err1
                elif isinstance(service, Service2):
                    expected = err2
                assert error == ControllerErrors.PurgeFailed(error=expected, service=service)
            mock_purge1.assert_called()
            mock_purge2.assert_called()


def test_start(mock_parsed: Mock) -> None:
    # Test that the logic for starting a controller from parsed command line arguments is correct.
    with mock.patch('signal.signal', autospec=True) as mock_signal:
        with mock.patch.multiple(Service1, start=mock.DEFAULT, stop=mock.DEFAULT) as mocks1:
            with mock.patch.multiple(Service2, start=mock.DEFAULT, stop=mock.DEFAULT) as mocks2:
                mock_start1 = mocks1['start']
                mock_stop1 = mocks1['stop']
                mock_start2 = mocks2['start']
                mock_stop2 = mocks2['stop']

                start_thread = Thread(target=cli.start, args=(mock_parsed,))
                start_thread.start()

                # Wait for signal to be called. Wait at most one second.
                start_time = time.time()
                while len(mock_signal.call_args_list) < 2 and time.time() < start_time + 1:
                    time.sleep(0.01)

                # Check that signal handlers setup correctly.
                calls = mock_signal.call_args_list
                assert len(calls) == 2

                # Check that appropriate signals are handled.
                assert {calls[0].args[0], calls[1].args[0]} == {signal.SIGINT, signal.SIGTERM}

                # Check that same callable given o both signal handlers.
                signal_handler = calls[0].args[1]
                assert calls[1].args[1] == signal_handler

                # Wait a second, then check that the thread is alive and that start methods are called while stop
                # methods have not been called yet.
                time.sleep(1)
                assert start_thread.is_alive()
                mock_start1.assert_called()
                mock_start2.assert_called()
                mock_stop1.assert_not_called()
                mock_stop2.assert_not_called()

                # Now call to signal handler to stop the controller.
                signal_handler()

                # Allow half a second (very generous since there is not stop logic for the services) for thread to
                # terminate, and then check that stop methods were called.
                start_thread.join(0.5)
                assert not start_thread.is_alive()
                mock_stop1.assert_called()
                mock_stop2.assert_called()
