# Agent-facing messenger tool — Phase 4: send, check, reply, forward, broadcast, list_sessions, switch_session
import yaml
import os
from pathlib import Path
from helpers.tool import Tool, Response
from usr.plugins.a0_comms.helpers.mailbox import Mailbox
from usr.plugins.a0_comms.helpers.message_schema import Message
from usr.plugins.a0_comms.helpers.bus import MessageBus
from usr.plugins.a0_comms.helpers.config import MessengerConfig

class MessengerTool(Tool):
    """Inter-session messaging tool. Actions: send, check, check_session, reply, forward, broadcast, list_sessions, switch_session."""

    async def execute(self, **kwargs) -> Response:
        # Check if messenger is enabled in config
        config = self._config
        enabled = config.get("enabled", True) if isinstance(config, dict) else config.enabled if hasattr(config, 'enabled') else True
        if not enabled:
            return Response(
                message="Error: Messenger is disabled in configuration.",
                break_loop=False
            )

        action = kwargs.get("action", "")

        if action == "send":
            return await self._send(kwargs)
        elif action == "check":
            return await self._check(kwargs)
        elif action == "check_session":
            return await self._check_session(kwargs)
        elif action == "reply":
            return await self._reply(kwargs)
        elif action == "list_sessions":
            return await self._list_sessions()
        elif action == "forward":
            return await self._forward(kwargs)
        elif action == "broadcast":
            return await self._broadcast(kwargs)
        elif action == "switch_session":
            return await self._switch_session(kwargs)
        else:
            return Response(
                message=f"Unknown action: {action}. Available: send, check, check_session, reply, forward, broadcast, list_sessions, switch_session.",
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

        # Cross-project permission check
        allowed, reason = self._check_cross_project_permission(from_session, to_session)
        if not allowed:
            return Response(message=f"Error: {reason}", break_loop=False)

        msg = Message(
            from_session=from_session,
            to_session=to_session,
            from_agent=from_agent,
            content=content,
            mode="async"
        )

        # Attempt live delivery via MessageBus, fallback to mailbox
        delivered = await self._deliver_or_store(to_session, msg)

        return Response(
            message=f"Message sent. ID: {msg.message_id}\nTo: {to_session}\nMode: {'live' if delivered else 'async (mailbox)'}",
            break_loop=False,
            additional={"message_id": msg.message_id, "status": "delivered" if delivered else "queued"}
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

    async def _check_session(self, args: dict) -> Response:
        """Read another session's mailbox without switching."""
        session_id = args.get("session_id", "")
        if not session_id:
            return Response(
                message="Error: 'session_id' is required for check_session.",
                break_loop=False
            )
        
        limit = int(args.get("limit", 20))
        mailbox = Mailbox()
        messages = await mailbox.check(session_id, mark_read=False, limit=limit)
        
        if not messages:
            return Response(
                message=f"No unread messages for {session_id}.",
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
            message=f"[{session_id}] Inbox ({len(messages)} messages):\n\n" + "\n\n".join(summary_lines),
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

        # Cross-project permission check
        allowed, reason = self._check_cross_project_permission(from_session, to_session)
        if not allowed:
            return Response(message=f"Error: {reason}", break_loop=False)

        msg = Message(
            thread_id=thread_id,
            from_session=from_session,
            to_session=to_session,
            from_agent=from_agent,
            content=content,
            mode="async"
        )

        delivered = await self._deliver_or_store(to_session, msg)

        return Response(
            message=f"Reply sent. ID: {msg.message_id}\nThread: {thread_id}\nTo: {to_session}",
            break_loop=False,
            additional={"message_id": msg.message_id, "thread_id": thread_id, "status": "replied"}
        )

    async def _switch_session(self, args: dict) -> Response:
        from usr.plugins.a0_comms.helpers.session_manager import SessionManager
        project = args.get("project", "")
        agent_profile = args.get("agent_profile", "default")
        message_text = args.get("message", "")
        timeout = int(args.get("timeout", 120))
        
        if not project or not message_text:
            return Response(
                message="Error: 'project' and 'message' are required for switch_session.",
                break_loop=False
            )
        
        result = await SessionManager.spawn_session(
            project=project,
            agent_profile=agent_profile,
            message=message_text,
            timeout=timeout
        )
        
        if result["timed_out"]:
            return Response(
                message=f"⚠ Session {result['session_id']} timed out after {timeout}s.\n"
                        f"The session may still be processing. Check its inbox later.",
                break_loop=False,
                additional={"session_id": result["session_id"], "status": "timeout"}
            )
        
        return Response(
            message=f"◈ [{result['session_id']}] ◈\n{result['response']}\n\n"
                    f"Session ID: {result['session_id']}\n"
                    f"Context ID: {result['context_id']}\n"
                    f"Reply to continue this session.",
            break_loop=False,
            additional={
                "session_id": result["session_id"],
                "context_id": result["context_id"],
                "status": "completed"
            }
        )

    async def _deliver_or_store(self, to_session: str, msg: Message) -> bool:
        """Attempt live delivery via MessageBus, fallback to mailbox.
        Returns True if delivered live, False if stored in mailbox.
        """
        try:
            mailbox = Mailbox()
            bus = MessageBus(mailbox, self.registry.registry)
            return await bus.inject_message(to_session, msg)
        except Exception:
            mailbox = Mailbox()
            await mailbox.store(to_session, msg)
            return False

    @property
    def _config(self):
        """Resolved configuration with inheritance.
        Attempts MessengerConfig with project/agent context.
        Falls back to direct _loaded_config for backward compat.
        """
        # Backward compat: if _loaded_config is set directly (e.g., in tests), use it
        if hasattr(self, '_loaded_config'):
            return self._loaded_config

        try:
            project_name = None
            agent_profile = None
            if hasattr(self, 'agent'):
                context_id = getattr(self.agent, 'context_id', '')
                if context_id:
                    project_name = self._extract_project(context_id)
                agent_profile = getattr(self.agent, 'profile_name', None)

            resolved = MessengerConfig(project_name=project_name, agent_profile=agent_profile)
            self._loaded_config = resolved
            return resolved
        except Exception:
            # Fallback to raw default_config.yaml
            config_path = Path(__file__).resolve().parent.parent / "default_config.yaml"
            if config_path.exists():
                with open(config_path) as f:
                    self._loaded_config = yaml.safe_load(f) or {}
            else:
                self._loaded_config = {}
            return self._loaded_config

    @staticmethod
    def _extract_project(session_id: str) -> str:
        """Extract project name from session_id like 'a0-circuit:conductor'."""
        if ":" in session_id:
            return session_id.split(":")[0]
        return session_id

    def _check_cross_project_permission(self, from_session: str, to_session: str) -> tuple:
        """Check if cross-project messaging is allowed.
        Returns (allowed: bool, reason: str).
        """
        from_project = self._extract_project(from_session)
        to_project = self._extract_project(to_session)
        if from_project == to_project:
            return (True, "")
        config = self._config
        if hasattr(config, 'allowed_cross_project_messages'):
            allowed_projects = config.allowed_cross_project_messages
        else:
            allowed_projects = config.get("allowed_cross_project_messages", [])
        if "*" in allowed_projects:
            return (True, "")
        if from_project in allowed_projects:
            return (True, "")
        return (False, f"Cross-project messaging blocked: '{from_project}' -> '{to_project}' not in allowed_cross_project_messages.")

    @property
    def registry(self):
        if not hasattr(self, '_registry'):
            from usr.plugins.a0_comms.helpers.registry import SessionRegistry
            self._registry = SessionRegistry.get_instance()
        return self._registry

    async def _list_sessions(self) -> Response:
        sessions = self.registry.list_active()
        if not sessions:
            return Response(message="No active sessions.", break_loop=False)
        lines = [f"- {sid}" for sid in sessions]
        return Response(message=f"Active sessions ({len(sessions)}):\n" + "\n".join(lines), break_loop=False)

    async def _forward(self, args: dict) -> Response:
        """Forward a message from own inbox to another session."""
        message_id = args.get("message_id", "")
        to_session = args.get("to_session", "")
        annotation = args.get("message", "")

        if not message_id or not to_session:
            return Response(
                message="Error: 'message_id' and 'to_session' are required for forward.",
                break_loop=False
            )

        session_id = getattr(self.agent, 'context_id', 'unknown')
        from_agent = getattr(self.agent, 'profile_name', 'unknown')

        mailbox = Mailbox()

        # Read own inbox and find the message
        all_msgs = await mailbox.check(session_id, mark_read=False, limit=1000)
        original_msg = None
        for m in all_msgs:
            if m.get("message_id") == message_id:
                original_msg = m
                break

        if not original_msg:
            return Response(
                message=f"Error: Message {message_id} not found in inbox.",
                break_loop=False
            )

        # Cross-project permission check
        allowed, reason = self._check_cross_project_permission(session_id, to_session)
        if not allowed:
            return Response(message=f"Error: {reason}", break_loop=False)

        # Build forwarded content with original thread_id preserved
        original_tid = original_msg.get("thread_id", "")
        forwarded_content = (
            f"[Forwarded from {original_msg['from_agent']} ({original_msg['from_session']})]\n"
            f"[Original thread: {original_tid}]\n"
            f"{original_msg['content']}"
        )
        if annotation:
            forwarded_content = f"{annotation}\n\n--- Forwarded message ---\n{forwarded_content}"

        msg = Message(
            from_session=session_id,
            to_session=to_session,
            from_agent=from_agent,
            content=forwarded_content,
            mode="forwarded"
        )

        delivered = await self._deliver_or_store(to_session, msg)

        return Response(
            message=f"Message forwarded. New ID: {msg.message_id}\nTo: {to_session}\nOriginal: {message_id}",
            break_loop=False,
            additional={
                "message_id": msg.message_id,
                "original_message_id": message_id,
                "original_thread_id": original_msg.get("thread_id"),
                "status": "forwarded"
            }
        )

    async def _broadcast(self, args: dict) -> Response:
        """Broadcast a message to all active sessions except self."""
        content = args.get("message", "")

        if not content:
            return Response(
                message="Error: 'message' is required for broadcast.",
                break_loop=False
            )

        session_id = getattr(self.agent, 'context_id', 'unknown')
        from_agent = getattr(self.agent, 'profile_name', 'unknown')

        active_sessions = self.registry.list_active()
        targets = [s for s in active_sessions if s != session_id]

        if not targets:
            return Response(
                message="No active sessions to broadcast.",
                break_loop=False
            )

        delivered_count = 0
        for target in targets:
            # Cross-project permission check
            allowed, _ = self._check_cross_project_permission(session_id, target)
            if not allowed:
                continue

            msg = Message(
                from_session=session_id,
                to_session=target,
                from_agent=from_agent,
                content=content,
                mode="broadcast"
            )
            try:
                await self._deliver_or_store(target, msg)
                delivered_count += 1
            except Exception:
                pass

        return Response(
            message=f"Broadcast sent to {delivered_count}/{len(targets)} active sessions.",
            break_loop=False,
            additional={"delivered_count": delivered_count, "target_count": len(targets), "status": "broadcast"}
        )
