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
from app.models.database import CampaignChange, Installation
from app.authorization.models import (
    BackstoryNoteGrant,
    CampaignInvitation,
    CampaignMembership,
    CharacterNoteGrant,
)
from sqlalchemy import inspect, text


DEVELOPMENT_TABLE_NAMES = (
    "installation",
    "app_user",
    "password_credential",
    "auth_session",
    "account_token",
    "login_throttle",
    "security_event",
    "campaign_membership",
    "campaign_invitation",
    "character_note_grant",
    "backstory_note_grant",
    "campaign_change",
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
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    campaign_columns = (
        {
            column["name"]
            for column in inspector.get_columns("campaign")
        }
        if "campaign" in table_names
        else set()
    )
    if "campaign" in table_names and "orphaned" not in campaign_columns:
        connection.execute(
            text(
                "ALTER TABLE campaign ADD COLUMN orphaned "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )

    security_event_columns = (
        {
            column["name"]
            for column in inspector.get_columns("security_event")
        }
        if "security_event" in table_names
        else set()
    )
    additions = {
        "campaign_id": "INTEGER",
        "reason": "VARCHAR",
        "outcome": "VARCHAR NOT NULL DEFAULT 'succeeded'",
        "used_elevation": "BOOLEAN NOT NULL DEFAULT FALSE",
    }
    for column_name, definition in additions.items():
        if (
            "security_event" in table_names
            and column_name not in security_event_columns
        ):
            connection.execute(
                text(
                    f"ALTER TABLE security_event ADD COLUMN "
                    f"{column_name} {definition}"
                )
            )

    note_access_additions = {
        "created_by_user_id": "INTEGER",
        "visibility": "VARCHAR NOT NULL DEFAULT 'campaign'",
        "access_owner_user_id": "INTEGER",
    }
    for table_name in ("characternote", "backstorynote"):
        if table_name not in table_names:
            continue
        note_columns = {
            column["name"]
            for column in inspector.get_columns(table_name)
        }
        for column_name, definition in note_access_additions.items():
            if column_name not in note_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN "
                        f"{column_name} {definition}"
                    )
                )

    revision_tables = (
        "campaign",
        "sessionnote",
        "person",
        "location",
        "faction",
        "characterprofile",
        "characternote",
        "backstorynote",
        "inventory",
    )
    for table_name in revision_tables:
        if table_name not in table_names:
            continue
        columns = {
            column["name"]
            for column in inspector.get_columns(table_name)
        }
        if "revision" not in columns:
            connection.execute(
                text(
                    f"ALTER TABLE {table_name} ADD COLUMN "
                    "revision INTEGER NOT NULL DEFAULT 1"
                )
            )
        if (
            table_name not in {"characternote", "backstorynote"}
            and "updated_at" not in columns
        ):
            connection.execute(
                text(
                    f"ALTER TABLE {table_name} ADD COLUMN "
                    "updated_at DATETIME NOT NULL "
                    "DEFAULT '1970-01-01 00:00:00'"
                )
            )
            connection.execute(
                text(
                    f"UPDATE {table_name} "
                    "SET updated_at = CURRENT_TIMESTAMP"
                )
            )

    membership_columns = (
        {
            column["name"]
            for column in inspector.get_columns("campaign_membership")
        }
        if "campaign_membership" in table_names
        else set()
    )
    if (
        "campaign_membership" in table_names
        and "change_cursor" not in membership_columns
    ):
        connection.execute(
            text(
                "ALTER TABLE campaign_membership ADD COLUMN "
                "change_cursor INTEGER NOT NULL DEFAULT 0"
            )
        )
