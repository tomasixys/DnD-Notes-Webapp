from __future__ import annotations

import unicodedata
import secrets
from collections.abc import Callable
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlmodel import Session, select

from app.models.database import AuthSession, PasswordCredential, User


MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 1024
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 64
PASSWORD_HASH_POLICY_VERSION = 1
USERNAME_PUNCTUATION = {"_", "-", "."}
DEFAULT_PASSWORD_HASHER = PasswordHasher()
DUMMY_PASSWORD_HASH = DEFAULT_PASSWORD_HASHER.hash(
    secrets.token_urlsafe(32)
)


class CredentialError(ValueError):
    """Base error for invalid or unusable local credentials."""


class UsernamePolicyError(CredentialError):
    """Raised when a local username does not meet policy."""


class PasswordPolicyError(CredentialError):
    """Raised when a password does not meet policy."""


class CredentialStateError(CredentialError):
    """Raised when a credential cannot be attached to the requested user."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_username(username: str) -> str:
    normalized = unicodedata.normalize("NFKC", username.strip()).casefold()
    if not MIN_USERNAME_LENGTH <= len(normalized) <= MAX_USERNAME_LENGTH:
        raise UsernamePolicyError(
            f"Username must contain {MIN_USERNAME_LENGTH} to "
            f"{MAX_USERNAME_LENGTH} characters."
        )
    if not normalized[0].isalnum():
        raise UsernamePolicyError(
            "Username must begin with a letter or number."
        )
    if any(
        not (character.isalnum() or character in USERNAME_PUNCTUATION)
        for character in normalized
    ):
        raise UsernamePolicyError(
            "Username may contain letters, numbers, periods, hyphens, "
            "and underscores."
        )
    return normalized


def validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise PasswordPolicyError("Password must be text.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must contain at least {MIN_PASSWORD_LENGTH} "
            "characters."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must contain at most {MAX_PASSWORD_LENGTH} "
            "characters."
        )


class CredentialService:
    def __init__(
        self,
        db: Session,
        *,
        password_hasher: PasswordHasher | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.password_hasher = password_hasher or DEFAULT_PASSWORD_HASHER
        self.clock = clock or utc_now

    def set_password(
        self,
        user: User,
        password: str,
        *,
        revoke_sessions: bool = True,
    ) -> PasswordCredential:
        if user.id is None:
            raise CredentialStateError(
                "User must be persisted before assigning a password."
            )
        if not user.can_login:
            raise CredentialStateError(
                "A non-login user cannot receive a password."
            )
        validate_password(password)
        changed_at = self.clock()
        encoded_hash = self.password_hasher.hash(password)
        credential = self.db.get(PasswordCredential, user.id)
        if credential is None:
            credential = PasswordCredential(
                user_id=user.id,
                password_hash=encoded_hash,
                hash_policy_version=PASSWORD_HASH_POLICY_VERSION,
                password_changed_at=changed_at,
            )
            self.db.add(credential)
        else:
            credential.password_hash = encoded_hash
            credential.hash_policy_version = PASSWORD_HASH_POLICY_VERSION
            credential.password_changed_at = changed_at
            credential.failed_attempts = 0
            credential.last_failed_at = None
            credential.locked_until = None
            self.db.add(credential)
        if revoke_sessions:
            self.revoke_sessions(user.id, revoked_at=changed_at)
        self.db.flush()
        return credential

    def verify_password(
        self,
        credential: PasswordCredential,
        password: str,
    ) -> bool:
        try:
            valid = self.password_hasher.verify(
                credential.password_hash,
                password,
            )
        except (InvalidHashError, VerificationError):
            return False
        if not valid:
            return False
        if self.password_hasher.check_needs_rehash(
            credential.password_hash
        ):
            credential.password_hash = self.password_hasher.hash(password)
            credential.hash_policy_version = PASSWORD_HASH_POLICY_VERSION
            credential.password_changed_at = self.clock()
            self.db.add(credential)
            self.db.flush()
        return True

    def revoke_sessions(
        self,
        user_id: int,
        *,
        revoked_at: datetime | None = None,
    ) -> int:
        timestamp = revoked_at or self.clock()
        sessions = self.db.exec(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
        for session in sessions:
            session.revoked_at = timestamp
            self.db.add(session)
        return len(sessions)
