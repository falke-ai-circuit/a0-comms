# MessageBus — routes messages to live sessions or fallback to mailbox
from .message_schema import Message
from .mailbox import Mailbox
from .registry import Registry

try:
    from agent import UserMessage
except ImportError:
    UserMessage = None


class MessageBus:
    """Routes messages between sessions via direct injection or async mailbox."""

    def __init__(self, mailbox: Mailbox, registry: Registry):
        self.mailbox = mailbox
        self.registry = registry

    async def inject_message(self, to_session: str, message: Message) -> bool:
        """
        Try direct injection into live agent, fallback to mailbox.
        Returns True if delivered directly, False if stored in mailbox.
        """
        session = self.registry.get(to_session)
        if session and UserMessage:
            agent_instance = session.get("agent_instance")
            if agent_instance and hasattr(agent_instance, "context"):
                try:
                    agent_instance.context.communicate(UserMessage(message.content))
                    return True
                except Exception:
                    pass

        # Fallback to mailbox
        await self.mailbox.store(to_session, message)
        return False
