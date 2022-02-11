from collections.abc import Callable

from enough import JSONType
from keywordcommands import DefaultCommandHandler
from keywordcommands.exceptions import CommandErrors

from servicecontrol.slack.cmds.state import SlackCommandsState


class SlackCommandsHandler(DefaultCommandHandler):
    """:class:`.CommandHandler` which handles Slack commands."""
    def handle_error(self, state: SlackCommandsState) -> None:
        """Handle the situation in which an error occurred when handling a command.

        :param state: State to handle the error with.
        """
        super().handle_error(state)
        if isinstance(state.query.error is CommandErrors.UnexpectedError):
            # Log unexpected errors.
            state.log.error(str(state.query.error))

    def handle_slash(self, ack: Callable[[], object], command: JSONType, state: SlackCommandsState) -> None:
        """Handle an incoming Slack slash command.

        :param ack: Callable to call to acknowledge receipt of the command.
        :param command: JSON command object receive from Slack.
        :param state: State to handle the command with.
        """
        ack()
        state.reset()
        state.command = command
        self.handle(state, command['text'])

    def register(self, state: SlackCommandsState) -> None:
        """Use the given Slack Bolt application and state to register this.

        :param state: :class:`.SlackCommandState` to register with.
        """
        state.bolt.command(state.query.name)(lambda ack, command: self.handle_slash(ack, command, state))
