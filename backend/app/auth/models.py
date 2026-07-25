from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Enum as SAEnum, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.auth.enums import (
    AccountTokenPurpose,
    SecurityEventType,
    SystemRole,
    UserStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def string_enum(enum_type, name: str) -> SAEnum:
    return SAEnum(
        enum_type,
        values_callable=lambda enum: [member.value for member in enum],
        native_enum=False,
        create_constraint=True,
        name=name,
    )


class User(SQLModel, table=True):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint(
            "normalized_username",
            name="uq_app_user_normalized_username",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    username: str
    normalized_username: str = Field(index=True)
    display_name: str = ""
    email: str | None = None
    normalized_email: str | None = Field(default=None, index=True)
    status: UserStatus = Field(
        default=UserStatus.PENDING,
        sa_type=string_enum(UserStatus, "user_status"),
    )
    system_role: SystemRole = Field(
        default=SystemRole.USER,
        sa_type=string_enum(SystemRole, "system_role"),
    )
    can_login: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = None


class PasswordCredential(SQLModel, table=True):
    __tablename__ = "password_credential"
    __table_args__ = (
        CheckConstraint(
            "failed_attempts >= 0",
            name="ck_password_credential_failed_attempts",
        ),
        CheckConstraint(
            "hash_policy_version >= 1",
            name="ck_password_credential_policy_version",
        ),
    )

    user_id: int = Field(
        foreign_key="app_user.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    password_hash: str
    hash_policy_version: int = 1
    password_changed_at: datetime = Field(default_factory=utc_now)
    failed_attempts: int = 0
    last_failed_at: datetime | None = None
    locked_until: datetime | None = None


class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_session"
    __table_args__ = (
        UniqueConstraint(
            "token_digest",
            name="uq_auth_session_token_digest",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="app_user.id",
        ondelete="CASCADE",
        index=True,
    )
    token_digest: str = Field(index=True)
    csrf_token_digest: str
    created_at: datetime = Field(default_factory=utc_now)
    last_used_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None
    created_ip: str | None = None
    last_ip: str | None = None


class AccountToken(SQLModel, table=True):
    __tablename__ = "account_token"
    __table_args__ = (
        UniqueConstraint(
            "token_digest",
            name="uq_account_token_digest",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="app_user.id",
        ondelete="CASCADE",
        index=True,
    )
    purpose: AccountTokenPurpose = Field(
        sa_type=string_enum(AccountTokenPurpose, "account_token_purpose"),
    )
    token_digest: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    consumed_at: datetime | None = None
    created_by_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )


class LoginThrottle(SQLModel, table=True):
    __tablename__ = "login_throttle"
    __table_args__ = (
        CheckConstraint(
            "failed_attempts >= 0",
            name="ck_login_throttle_failed_attempts",
        ),
    )

    source_digest: str = Field(primary_key=True)
    failed_attempts: int = 0
    window_started_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    locked_until: datetime | None = None


class SecurityEvent(SQLModel, table=True):
    __tablename__ = "security_event"

    id: int | None = Field(default=None, primary_key=True)
    event_type: SecurityEventType = Field(
        sa_type=string_enum(SecurityEventType, "security_event_type"),
        index=True,
    )
    user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )
    actor_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )
    source_digest: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
