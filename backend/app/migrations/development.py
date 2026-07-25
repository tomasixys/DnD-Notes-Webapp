"""Temporary schema work for the next unreleased database version.

Development migrations must be idempotent and based on schema inspection
because they run without changing the released SQLite ``PRAGMA user_version``
or the portable Alembic revision. Before release, move their final behavior
into a numbered migration and restore this function to a no-op.
"""

from sqlmodel import SQLModel

from app.auth.models import (
    AccountToken,
    AuthSession,
    LoginThrottle,
    PasswordCredential,
    SecurityEvent,
    User,
)
from app.models.database import Installation


DEVELOPMENT_TABLE_NAMES = (
    "installation",
    "app_user",
    "password_credential",
    "auth_session",
    "account_token",
    "login_throttle",
    "security_event",
)


def migrate_development_schema(connection) -> None:
    """Create unreleased installation and identity tables idempotently."""
    tables = [
        SQLModel.metadata.tables[name]
        for name in DEVELOPMENT_TABLE_NAMES
    ]
    SQLModel.metadata.create_all(
        bind=connection,
        tables=tables,
        checkfirst=True,
    )
