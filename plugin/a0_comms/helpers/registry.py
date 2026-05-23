# In-memory session registry for live delivery
from datetime import datetime, timezone, timedelta

class Registry:
    """In-memory session registry mapping session_id to live agent info."""

    def __init__(self, timeout_seconds: int = 300):
        self._sessions: dict = {}
        self.timeout = timeout_seconds

    def register(self, session_id: str, context_id: str, agent_instance, project: str = "") -> None:
        """Store or update session info, set last_seen to now."""
        self._sessions[session_id] = {
            "context_id": context_id,
            "agent_instance": agent_instance,
            "project": project,
            "last_seen": datetime.now(timezone.utc)
        }

    def unregister(self, session_id: str) -> bool:
        """Remove session from registry. Returns True if found."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get(self, session_id: str) -> dict | None:
        """Return session dict or None if not found or stale."""
        entry = self._sessions.get(session_id)
        if not entry:
            return None
        age = datetime.now(timezone.utc) - entry["last_seen"]
        if age > timedelta(seconds=self.timeout):
            return None
        return entry

    def list_active(self) -> list[str]:
        """Return list of non-stale session IDs."""
        now = datetime.now(timezone.utc)
        active = []
        for sid, entry in self._sessions.items():
            age = now - entry["last_seen"]
            if age <= timedelta(seconds=self.timeout):
                active.append(sid)
        return active
