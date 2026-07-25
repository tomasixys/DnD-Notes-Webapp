"""Temporary schema work for the next unreleased database version.

Development migrations must be idempotent and based on schema inspection
because they run without changing the released SQLite ``PRAGMA user_version``
or the portable Alembic revision. Before release, move their final behavior
into a numbered migration and restore this function to a no-op.
"""

from sqlmodel import SQLModel

from app.models.database import (
    AccountToken,
    AuthSession,
    Installation,
    PasswordCredential,
    User,
)


DEVELOPMENT_TABLE_NAMES = (
    "installation",
    "app_user",
    "password_credential",
    "auth_session",
    "account_token",
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
