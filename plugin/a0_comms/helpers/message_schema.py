# Helpers for message serialization
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid

@dataclass
class Message:
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    thread_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_session: str = ""
    to_session: str = ""
    from_agent: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "unread"
    mode: str = "async"
    content: str = ""

    def serialize(self):
        return asdict(self)

    @classmethod
    def deserialize(cls, data: dict):
        return cls(**data)
