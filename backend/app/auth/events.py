from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlmodel import Session

from app.auth.enums import SecurityEventType
from app.auth.models import SecurityEvent
from app.auth.passwords import utc_now


class SecurityEventService:
    def __init__(
        self,
        db: Session,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.clock = clock or utc_now

    def record(
        self,
        event_type: SecurityEventType,
        *,
        user_id: int | None = None,
        actor_user_id: int | None = None,
        source_digest: str | None = None,
    ) -> SecurityEvent:
        event = SecurityEvent(
            event_type=event_type,
            user_id=user_id,
            actor_user_id=actor_user_id,
            source_digest=source_digest,
            created_at=self.clock(),
        )
        self.db.add(event)
        self.db.flush()
        return event
