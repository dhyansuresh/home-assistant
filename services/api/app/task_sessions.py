"""In-memory storage for HomePilot task sessions."""

from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4

from app.schemas import TaskSession, TaskSessionMode, TaskSessionState


class TaskSessionStore:
    """Store task sessions in this FastAPI process."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._sessions: dict[UUID, TaskSession] = {}
        self._lock = Lock()

    def create(self, mode: TaskSessionMode) -> TaskSession:
        """Create, store, and return a new task session."""
        session = TaskSession(
            session_id=uuid4(),
            mode=mode,
            state=TaskSessionState.COLLECTING,
            revision=0,
            expires_at=datetime.now(UTC) + self._ttl,
        )

        with self._lock:
            self._sessions[session.session_id] = session

        return session.model_copy(deep=True)

    def get(self, session_id: UUID) -> TaskSession | None:
        """Return a stored session, or None when it does not exist."""
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            return None

        return session.model_copy(deep=True)
