"""Temporary schema work for the next unreleased database version.

Development migrations must be idempotent and based on schema inspection
because they run without changing ``PRAGMA user_version``. Before release,
move their final behavior into the next numbered module and restore this
function to a no-op.
"""

from sqlalchemy import inspect, text


def migrate_development_schema(connection) -> None:
    """Add the persisted installation identity for the unreleased version."""
    existing_tables = set(inspect(connection).get_table_names())
    if "installation" not in existing_tables:
        connection.execute(
            text(
                "CREATE TABLE installation ("
                "id INTEGER NOT NULL PRIMARY KEY, "
                "installation_id VARCHAR NOT NULL, "
                "mode VARCHAR NOT NULL, "
                "initialized_at DATETIME NOT NULL, "
                "CONSTRAINT ck_installation_singleton CHECK (id = 1)"
                ")"
            )
        )

    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ix_installation_installation_id "
            "ON installation (installation_id)"
        )
    )
