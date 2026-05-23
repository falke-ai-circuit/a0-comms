# JSONL-based mailbox storage
import json
import aiofiles
import os
from pathlib import Path
from .message_schema import Message

class Mailbox:
    BASE_DIR = Path("/a0/usr/plugins/a0_comms/mailboxes/")

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or self.BASE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _mailbox_path(self, session_id: str) -> Path:
        safe = session_id.replace("/", "_").replace(":", "-")
        return self.base_dir / f"{safe}.jsonl"

    async def store(self, session_id: str, message: Message) -> str:
        path = self._mailbox_path(session_id)
        async with aiofiles.open(path, "a") as f:
            await f.write(json.dumps(message.serialize()) + "\n")
        return message.message_id

    async def check(self, session_id: str, mark_read: bool = True, limit: int = 20) -> list[dict]:
        path = self._mailbox_path(session_id)
        if not path.exists():
            return []

        messages = []
        updated_lines = []
        async with aiofiles.open(path, "r") as f:
            async for line in f:
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                if msg["status"] == "unread":
                    if mark_read:
                        msg["status"] = "read"
                    messages.append(msg)
                updated_lines.append(json.dumps(msg))

        if mark_read and messages:
            async with aiofiles.open(path, "w") as f:
                for line in updated_lines:
                    await f.write(line + "\n")

        return messages[-limit:]

    async def get_thread(self, session_id: str, thread_id: str) -> list[dict]:
        path = self._mailbox_path(session_id)
        if not path.exists():
            return []
        thread_messages = []
        async with aiofiles.open(path, "r") as f:
            async for line in f:
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                if msg.get("thread_id") == thread_id:
                    thread_messages.append(msg)
        return thread_messages
