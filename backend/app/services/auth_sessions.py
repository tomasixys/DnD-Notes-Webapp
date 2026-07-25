from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.database import AuthSession, User
from app.models.enums import UserStatus
from app.services.credentials import utc_now


SESSION_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class IssuedSession:
    session: AuthSession
    session_token: str
    csrf_token: str


class AuthSessionService:
    def __init__(
        self,
        db: Session,
        *,
        clock: Callable[[], datetime] | None = None,
        idle_lifetime_minutes: int = 720,
        absolute_lifetime_minutes: int = 10080,
        token_factory: Callable[[int], str] | None = None,
    ):
        self.db = db
        self.clock = clock or utc_now
        self.idle_lifetime = timedelta(minutes=idle_lifetime_minutes)
        self.absolute_lifetime = timedelta(
            minutes=absolute_lifetime_minutes
        )
        self.token_factory = token_factory or secrets.token_urlsafe

    def create(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        client_ip: str | None = None,
    ) -> IssuedSession:
        if (
            user.id is None
            or user.status is not UserStatus.ACTIVE
            or not user.can_login
        ):
            raise ValueError(
                "Sessions require an active, login-capable user."
            )
        now = self.clock()
        absolute_expires_at = now + self.absolute_lifetime
        session_token = self.token_factory(SESSION_TOKEN_BYTES)
        csrf_token = self.token_factory(CSRF_TOKEN_BYTES)
        session = AuthSession(
            user_id=user.id,
            token_digest=token_digest(session_token),
            csrf_token_digest=token_digest(csrf_token),
            created_at=now,
            last_used_at=now,
            expires_at=min(
                now + self.idle_lifetime,
                absolute_expires_at,
            ),
            absolute_expires_at=absolute_expires_at,
            user_agent=(user_agent or "")[:512] or None,
            created_ip=client_ip,
            last_ip=client_ip,
        )
        self.db.add(session)
        self.db.flush()
        return IssuedSession(
            session=session,
            session_token=session_token,
            csrf_token=csrf_token,
        )

    def resolve(
        self,
        session_token: str | None,
        *,
        client_ip: str | None = None,
    ) -> tuple[AuthSession, User] | None:
        if not session_token:
            return None
        session = self.db.exec(
            select(AuthSession).where(
                AuthSession.token_digest
                == token_digest(session_token)
            )
        ).first()
        if session is None or session.revoked_at is not None:
            return None
        now = self.clock()
        if (
            as_utc(session.expires_at) <= as_utc(now)
            or as_utc(session.absolute_expires_at) <= as_utc(now)
        ):
            session.revoked_at = now
            self.db.add(session)
            self.db.flush()
            return None
        user = self.db.get(User, session.user_id)
        if (
            user is None
            or user.status is not UserStatus.ACTIVE
            or not user.can_login
        ):
            session.revoked_at = now
            self.db.add(session)
            self.db.flush()
            return None
        session.last_used_at = now
        session.last_ip = client_ip
        session.expires_at = min(
            now + self.idle_lifetime,
            as_utc(session.absolute_expires_at),
        )
        self.db.add(session)
        self.db.flush()
        return session, user

    def rotate_csrf(self, session: AuthSession) -> str:
        csrf_token = self.token_factory(CSRF_TOKEN_BYTES)
        session.csrf_token_digest = token_digest(csrf_token)
        self.db.add(session)
        self.db.flush()
        return csrf_token

    @staticmethod
    def validate_csrf(
        session: AuthSession,
        csrf_token: str | None,
    ) -> bool:
        if not csrf_token:
            return False
        return hmac.compare_digest(
            session.csrf_token_digest,
            token_digest(csrf_token),
        )

    def revoke(self, session: AuthSession) -> None:
        if session.revoked_at is None:
            session.revoked_at = self.clock()
            self.db.add(session)
            self.db.flush()

    def revoke_all(self, user_id: int) -> int:
        sessions = self.db.exec(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
        now = self.clock()
        for session in sessions:
            session.revoked_at = now
            self.db.add(session)
        self.db.flush()
        return len(sessions)
