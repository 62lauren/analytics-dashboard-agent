import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Session:
    messages: list = field(default_factory=list)
    charts: list = field(default_factory=list)
    insights: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)


class SessionManager:
    SESSION_TTL = timedelta(hours=2)

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session()
        session = self._sessions[session_id]
        session.last_used = datetime.utcnow()
        return session

    def save(self, session_id: str, messages: list, charts: list, insights: list) -> None:
        session = self.get_or_create(session_id)
        session.messages = messages
        session.charts = charts
        session.insights = insights

    def cleanup_expired(self) -> None:
        cutoff = datetime.utcnow() - self.SESSION_TTL
        expired = [sid for sid, s in self._sessions.items() if s.last_used < cutoff]
        for sid in expired:
            del self._sessions[sid]


async def cleanup_loop(manager: SessionManager) -> None:
    while True:
        await asyncio.sleep(30 * 60)  # every 30 minutes
        manager.cleanup_expired()
