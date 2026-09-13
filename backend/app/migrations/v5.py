"""Migration from schema version 4 to schema version 5.

Version 5 removes the stored episode session number. Session numbers are now
derived by the frontend from the date-sorted active session list.
"""

from sqlalchemy import inspect, text


def migrate_to_v5(connection) -> None:
    inspector = inspect(connection)
    if "sessionnote" not in inspector.get_table_names():
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("sessionnote")
    }
    if "session_number" not in columns:
        return

    indexes = {
        index["name"]
        for index in inspector.get_indexes("sessionnote")
        if index["name"]
    }
    if "ix_sessionnote_session_number" in indexes:
        connection.execute(
            text("DROP INDEX ix_sessionnote_session_number")
        )
    connection.execute(
        text("ALTER TABLE sessionnote DROP COLUMN session_number")
    )
