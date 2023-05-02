from logging import Logger, LoggerAdapter

from enough import JSONType
from slack_bolt import App
from slack_sdk import WebClient

from keywordcommands import (
    CommandGroup,
    DefaultQueryFormatter,
    QueryFormatter,
    SecurityManager,
    UserState
)


class SlackCommandsState(UserState[str]):
    """CommandState which has a Slack Bolt application object."""

    #: Slack bolt application to use.
    bolt: App

    #: Command JSON received from Slack.
    command: JSONType

    #: Logger to use to log errors and informational messages.
    log: Logger | LoggerAdapter

    def __init__(
        self,
        name: str,
        root: CommandGroup,
        *,
        bolt: App,
        log: Logger | LoggerAdapter,
        formatter: QueryFormatter = DefaultQueryFormatter(),
        security_manager: SecurityManager = SecurityManager()
    ) -> None:
        """Initialize the state with the given properties.

        :param name: Name of the slash command.
        :param root: Root command group to use.
        :param bolt: Slack bolt application object to use.
        :param log: Logger to use to log errors and informational messages.
        :param formatter: Formatter to use to format :class:`.QueryInfo`
            instances.
        :param security_manager: Security manager to use.
        """
        super().__init__(
            name,
            root,
            formatter=formatter,
            messenger=self.user_msg,
            security_manager=security_manager
        )
        self.bolt = bolt
        self.command = None
        self.log = log

    @property
    def channel(self) -> str:
        """Gives the channel the command was called in.

        :return: Channel the command was called in.
        """
        return self.command['channel_id']

    @property
    def slack(self) -> WebClient:
        """Gives the underlying Slack client for the Bolt application

        :return: Underlying Slack client.
        """
        return self.bolt.client

    @property
    def user(self) -> str:
        """Gives the Slack user ID of the command caller.

        :return: Slack user ID of the command caller.
        """
        return self.command['user_id']

    def user_msg(self, msg: str, user_id: str = '') -> None:
        """Sends the given message to the given user on Slack.

        :param msg: Message to send.
        :param user_id: ID of user to send message to. If unspecified, sent to
            the calling user.
        """
        self.bolt.client.chat_postMessage(
            channel=user_id or self.user, text=msg
        )
