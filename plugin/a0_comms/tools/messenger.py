# Agent-facing messenger tool — Phase 1: send, check, reply only
from helpers.tool import Tool, Response
from usr.plugins.a0_comms.helpers.mailbox import Mailbox
from usr.plugins.a0_comms.helpers.message_schema import Message

class MessengerTool(Tool):
    """Inter-session messaging tool. Actions: send, check, reply."""

    async def execute(self, **kwargs) -> Response:
        action = kwargs.get("action", "")

        if action == "send":
            return await self._send(kwargs)
        elif action == "check":
            return await self._check(kwargs)
        elif action == "reply":
            return await self._reply(kwargs)
        else:
            return Response(
                message=f"Unknown action: {action}. Available: send, check, reply.",
                break_loop=False
            )

    async def _send(self, args: dict) -> Response:
        to_session = args.get("to_session", "")
        content = args.get("message", "")

        if not to_session or not content:
            return Response(
                message="Error: 'to_session' and 'message' are required for send.",
                break_loop=False
            )

        # Get sender info from agent context
        from_session = getattr(self.agent, 'context_id', 'unknown')
        from_agent = getattr(self.agent, 'profile_name', 'unknown')

        msg = Message(
            from_session=from_session,
            to_session=to_session,
            from_agent=from_agent,
            content=content,
            mode="async"
        )

        mailbox = Mailbox()
        message_id = await mailbox.store(to_session, msg)

        return Response(
            message=f"Message sent. ID: {message_id}\nTo: {to_session}\nMode: async (mailbox)",
            break_loop=False,
            additional={"message_id": message_id, "status": "queued"}
        )

    async def _check(self, args: dict) -> Response:
        # Check own session's mailbox
        session_id = getattr(self.agent, 'context_id', 'unknown')
        limit = int(args.get("limit", 20))

        mailbox = Mailbox()
        messages = await mailbox.check(session_id, mark_read=True, limit=limit)

        if not messages:
            return Response(
                message="Inbox empty.",
                break_loop=False
            )

        summary_lines = []
        for i, msg in enumerate(messages, 1):
            summary_lines.append(
                f"[{i}] From: {msg['from_agent']} ({msg['from_session']})\n"
                f"    Thread: {msg['thread_id']}\n"
                f"    Time: {msg['timestamp']}\n"
                f"    Content: {msg['content'][:200]}"
            )

        return Response(
            message=f"Inbox ({len(messages)} messages):\n\n" + "\n\n".join(summary_lines),
            break_loop=False
        )

    async def _reply(self, args: dict) -> Response:
        thread_id = args.get("thread_id", "")
        content = args.get("message", "")

        if not thread_id or not content:
            return Response(
                message="Error: 'thread_id' and 'message' are required for reply.",
                break_loop=False
            )

        # Look up the thread to find original sender
        session_id = getattr(self.agent, 'context_id', 'unknown')
        mailbox = Mailbox()
        thread_msgs = await mailbox.get_thread(session_id, thread_id)

        if not thread_msgs:
            return Response(
                message=f"Error: Thread {thread_id} not found in inbox.",
                break_loop=False
            )

        # Reply goes to the original sender
        original = thread_msgs[0]
        to_session = original["from_session"]
        from_session = session_id
        from_agent = getattr(self.agent, 'profile_name', 'unknown')

        msg = Message(
            thread_id=thread_id,
            from_session=from_session,
            to_session=to_session,
            from_agent=from_agent,
            content=content,
            mode="async"
        )

        message_id = await mailbox.store(to_session, msg)

        return Response(
            message=f"Reply sent. ID: {message_id}\nThread: {thread_id}\nTo: {to_session}",
            break_loop=False,
            additional={"message_id": message_id, "thread_id": thread_id, "status": "replied"}
        )
