from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from argon2 import PasswordHasher
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.database import PasswordCredential, User
from app.models.enums import SystemRole, UserStatus
from app.services.credentials import (
    CredentialService,
    CredentialStateError,
    normalize_username,
    utc_now,
)


SYSTEM_CUSTODIAN_USERNAME = "system-custodian"


class IdentityAdminError(RuntimeError):
    """Raised when an offline identity administration operation is unsafe."""


class IdentityAdminService:
    def __init__(
        self,
        db: Session,
        *,
        password_hasher: PasswordHasher | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.clock = clock or utc_now
        self.credentials = CredentialService(
            db,
            password_hasher=password_hasher,
            clock=self.clock,
        )

    def create_initial_admin(
        self,
        username: str,
        password: str,
    ) -> User:
        existing_admin = self.db.exec(
            select(User).where(
                User.system_role == SystemRole.ADMIN,
                User.status == UserStatus.ACTIVE,
                User.can_login.is_(True),
            )
        ).first()
        if existing_admin is not None:
            raise IdentityAdminError(
                "An enabled login-capable system administrator already "
                "exists. Add later administrators through the authenticated "
                "administration workflow."
            )

        normalized = normalize_username(username)
        if self._find_user(normalized) is not None:
            raise IdentityAdminError("That username is already in use.")

        now = self.clock()
        admin = User(
            username=username.strip(),
            normalized_username=normalized,
            status=UserStatus.ACTIVE,
            system_role=SystemRole.ADMIN,
            can_login=True,
            created_at=now,
            updated_at=now,
        )
        self.db.add(admin)
        self.db.flush()
        self.credentials.set_password(
            admin,
            password,
            revoke_sessions=False,
        )
        self._ensure_custodian(now)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise IdentityAdminError(
                "The initial administrator could not be created because "
                "its username or installation identity already exists."
            ) from error
        self.db.refresh(admin)
        return admin

    def reset_password(self, username: str, password: str) -> User:
        normalized = normalize_username(username)
        user = self._find_user(normalized)
        if user is None or user.status is UserStatus.DELETED:
            raise IdentityAdminError("No resettable user has that username.")
        if not user.can_login or user.system_role is SystemRole.CUSTODIAN:
            raise IdentityAdminError(
                "That account is not allowed to authenticate."
            )
        try:
            self.credentials.set_password(user, password)
        except CredentialStateError as error:
            raise IdentityAdminError(str(error)) from error
        user.updated_at = self.clock()
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _find_user(self, normalized_username: str) -> User | None:
        return self.db.exec(
            select(User).where(
                User.normalized_username == normalized_username
            )
        ).first()

    def _ensure_custodian(self, now: datetime) -> User:
        custodian = self.db.exec(
            select(User).where(
                User.system_role == SystemRole.CUSTODIAN
            )
        ).first()
        if custodian is not None:
            return custodian
        custodian = User(
            username=SYSTEM_CUSTODIAN_USERNAME,
            normalized_username=SYSTEM_CUSTODIAN_USERNAME,
            display_name="System Custodian",
            status=UserStatus.ACTIVE,
            system_role=SystemRole.CUSTODIAN,
            can_login=False,
            created_at=now,
            updated_at=now,
        )
        self.db.add(custodian)
        self.db.flush()
        if self.db.get(PasswordCredential, custodian.id) is not None:
            raise IdentityAdminError(
                "System custodian unexpectedly has a password credential."
            )
        return custodian
