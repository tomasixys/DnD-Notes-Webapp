from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth.models import LoginThrottle
from app.auth.passwords import utc_now


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def source_digest(source: str | None, secret: str) -> str:
    normalized = (source or "unknown").strip().casefold()
    return hmac.new(
        secret.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class LoginThrottleService:
    def __init__(
        self,
        db: Session,
        *,
        failure_limit: int,
        window_seconds: int,
        lock_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.failure_limit = failure_limit
        self.window = timedelta(seconds=window_seconds)
        self.lock_duration = timedelta(seconds=lock_seconds)
        self.clock = clock or utc_now

    def is_allowed(self, digest: str) -> bool:
        throttle = self._get_for_update(digest)
        if throttle is None or throttle.locked_until is None:
            return True
        return as_utc(throttle.locked_until) <= as_utc(self.clock())

    def record_failure(self, digest: str) -> bool:
        now = self.clock()
        throttle = self._get_for_update(digest)
        if throttle is None:
            throttle = LoginThrottle(
                source_digest=digest,
                failed_attempts=0,
                window_started_at=now,
                updated_at=now,
            )
            try:
                with self.db.begin_nested():
                    self.db.add(throttle)
                    self.db.flush()
            except IntegrityError:
                throttle = self._get_for_update(digest)
                if throttle is None:
                    raise
        elif as_utc(now) - as_utc(
            throttle.window_started_at
        ) >= self.window:
            throttle.failed_attempts = 0
            throttle.window_started_at = now
            throttle.locked_until = None

        throttle.failed_attempts += 1
        throttle.updated_at = now
        if throttle.failed_attempts >= self.failure_limit:
            throttle.locked_until = now + self.lock_duration
        self.db.add(throttle)
        self.db.flush()
        return (
            throttle.locked_until is not None
            and as_utc(throttle.locked_until) > as_utc(now)
        )

    def record_success(self, digest: str) -> None:
        throttle = self._get_for_update(digest)
        if throttle is not None:
            self.db.delete(throttle)
            self.db.flush()

    def _get_for_update(self, digest: str) -> LoginThrottle | None:
        return self.db.exec(
            select(LoginThrottle)
            .where(LoginThrottle.source_digest == digest)
            .with_for_update()
        ).first()
