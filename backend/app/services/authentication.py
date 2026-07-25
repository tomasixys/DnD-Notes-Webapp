from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlmodel import Session, select

from app.models.database import PasswordCredential, User
from app.models.enums import UserStatus
from app.services.credentials import (
    DUMMY_PASSWORD_HASH,
    CredentialService,
    normalize_username,
    utc_now,
)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AuthenticationService:
    def __init__(
        self,
        db: Session,
        *,
        password_hasher: PasswordHasher | None = None,
        dummy_password_hash: str | None = None,
        clock: Callable[[], datetime] | None = None,
        failure_limit: int = 5,
        initial_lock_seconds: int = 30,
        maximum_lock_seconds: int = 900,
    ):
        self.db = db
        self.clock = clock or utc_now
        self.credentials = CredentialService(
            db,
            password_hasher=password_hasher,
            clock=self.clock,
        )
        self.dummy_password_hash = (
            dummy_password_hash or DUMMY_PASSWORD_HASH
        )
        self.failure_limit = failure_limit
        self.initial_lock_seconds = initial_lock_seconds
        self.maximum_lock_seconds = maximum_lock_seconds

    def authenticate(self, username: str, password: str) -> User | None:
        try:
            normalized = normalize_username(username)
        except ValueError:
            self._verify_dummy(password)
            return None

        user = self.db.exec(
            select(User).where(
                User.normalized_username == normalized
            )
        ).first()
        credential = (
            self.db.get(PasswordCredential, user.id)
            if user is not None and user.id is not None
            else None
        )
        if user is None or credential is None:
            self._verify_dummy(password)
            return None

        now = self.clock()
        valid_password = self.credentials.verify_password(
            credential,
            password,
        )
        if (
            credential.locked_until is not None
            and as_utc(credential.locked_until) > as_utc(now)
        ):
            return None
        if not valid_password:
            self._record_failure(credential, now)
            return None
        if (
            user.status is not UserStatus.ACTIVE
            or not user.can_login
        ):
            return None

        credential.failed_attempts = 0
        credential.last_failed_at = None
        credential.locked_until = None
        self.db.add(credential)
        self.db.flush()
        return user

    def _record_failure(
        self,
        credential: PasswordCredential,
        failed_at: datetime,
    ) -> None:
        credential.failed_attempts += 1
        credential.last_failed_at = failed_at
        if credential.failed_attempts >= self.failure_limit:
            exponent = min(
                credential.failed_attempts - self.failure_limit,
                16,
            )
            lock_seconds = min(
                self.initial_lock_seconds * (2**exponent),
                self.maximum_lock_seconds,
            )
            credential.locked_until = failed_at + timedelta(
                seconds=lock_seconds
            )
        self.db.add(credential)
        self.db.flush()

    def _verify_dummy(self, password: str) -> None:
        try:
            self.credentials.password_hasher.verify(
                self.dummy_password_hash,
                password,
            )
        except (InvalidHashError, VerificationError):
            pass
