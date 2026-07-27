"""Migration from schema version 4 to schema version 5.

Version 5 drops the unused player_character column from the campaign table.
"""

from sqlalchemy import inspect, text


def migrate_to_v5(connection) -> None:
    inspector = inspect(connection)
    if not inspector.has_table("campaign"):
        return

    columns = [
        column["name"]
        for column in inspector.get_columns("campaign")
    ]
    if "player_character" in columns:
        connection.execute(
            text("ALTER TABLE campaign DROP COLUMN player_character")
        )
