"""Temporary schema work for the next unreleased database version.

Development migrations must be idempotent and based on schema inspection
because they run without changing ``PRAGMA user_version``. Before release,
move their final behavior into the next numbered module and restore this
function to a no-op.
"""

from sqlalchemy import inspect, text


def _create_character_note_table(connection, table_name: str) -> None:
    connection.execute(
        text(
            f"CREATE TABLE {table_name} ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "campaign_id INTEGER NOT NULL, "
            "character_person_id INTEGER NOT NULL, "
            "title VARCHAR NOT NULL, "
            "content VARCHAR NOT NULL DEFAULT '', "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL, "
            "FOREIGN KEY(campaign_id) REFERENCES campaign (id) ON DELETE CASCADE, "
            "FOREIGN KEY(character_person_id) REFERENCES characterprofile (person_id) "
            "ON DELETE CASCADE"
            ")"
        )
    )


def _create_character_note_indexes(connection, table_name: str) -> None:
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{table_name}_campaign_id "
            f"ON {table_name} (campaign_id)"
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{table_name}_character_person_id "
            f"ON {table_name} (character_person_id)"
        )
    )


def _migrate_legacy_character_entries(connection) -> None:
    existing_tables = set(inspect(connection).get_table_names())
    if "characterentry" not in existing_tables:
        return

    unknown_types = connection.execute(
        text(
            "SELECT DISTINCT entry_type FROM characterentry "
            "WHERE LOWER(entry_type) NOT IN ('note', 'backstory')"
        )
    ).scalars().all()
    if unknown_types:
        raise RuntimeError(
            "Cannot migrate unknown character entry types: "
            + ", ".join(str(value) for value in unknown_types)
        )

    destinations = (
        ("characternote", "note", "character_note"),
        ("backstorynote", "backstory", "backstory_note"),
    )
    for table_name, legacy_type, resource_type in destinations:
        connection.execute(
            text(
                f"INSERT OR IGNORE INTO {table_name} "
                "(id, campaign_id, character_person_id, title, content, "
                "created_at, updated_at) "
                "SELECT id, campaign_id, character_person_id, title, content, "
                "created_at, updated_at FROM characterentry "
                "WHERE LOWER(entry_type) = :entry_type"
            ),
            {"entry_type": legacy_type},
        )
        connection.execute(
            text(
                "UPDATE tagassignment SET owner_type = :resource_type "
                "WHERE owner_type = 'character_entry' AND owner_id IN ("
                "SELECT id FROM characterentry "
                "WHERE LOWER(entry_type) = :entry_type)"
            ),
            {
                "resource_type": resource_type,
                "entry_type": legacy_type,
            },
        )
        connection.execute(
            text(
                "UPDATE tag SET reference_type = :resource_type, "
                "key = 'reference:' || :resource_type || ':' || reference_id "
                "WHERE reference_type = 'character_entry' "
                "AND reference_id IN ("
                "SELECT id FROM characterentry "
                "WHERE LOWER(entry_type) = :entry_type)"
            ),
            {
                "resource_type": resource_type,
                "entry_type": legacy_type,
            },
        )

    connection.execute(text("DROP TABLE characterentry"))


def _migrate_session_content(connection) -> None:
    inspector = inspect(connection)
    if "sessionnote" not in inspector.get_table_names():
        return

    columns = {
        column["name"] for column in inspector.get_columns("sessionnote")
    }
    if "content" not in columns:
        connection.execute(
            text(
                "ALTER TABLE sessionnote ADD COLUMN content VARCHAR "
                "NOT NULL DEFAULT ''"
            )
        )
    if "description" in columns:
        connection.execute(
            text(
                "UPDATE sessionnote SET content = description "
                "WHERE content = '' AND description IS NOT NULL"
            )
        )


def migrate_development_schema(connection) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    if not {"campaign", "person"}.issubset(existing_tables):
        return

    if "characterprofile" not in existing_tables:
        connection.execute(
            text(
                "CREATE TABLE characterprofile ("
                "person_id INTEGER NOT NULL PRIMARY KEY, "
                "short_bio VARCHAR NOT NULL DEFAULT '', "
                "appearance VARCHAR NOT NULL DEFAULT '', "
                "image_path VARCHAR NOT NULL DEFAULT '', "
                "FOREIGN KEY(person_id) REFERENCES person (id) ON DELETE CASCADE"
                ")"
            )
        )

    existing_tables = set(inspect(connection).get_table_names())
    for table_name in ("characternote", "backstorynote"):
        if table_name not in existing_tables:
            _create_character_note_table(connection, table_name)
        _create_character_note_indexes(connection, table_name)

    _migrate_legacy_character_entries(connection)
    _migrate_session_content(connection)

    campaign_columns = {
        column["name"]
        for column in inspect(connection).get_columns("campaign")
    }
    if "active_character_person_id" not in campaign_columns:
        connection.execute(
            text(
                "ALTER TABLE campaign ADD COLUMN active_character_person_id INTEGER "
                "REFERENCES characterprofile (person_id) ON DELETE SET NULL"
            )
        )

    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_campaign_active_character_person_id "
            "ON campaign (active_character_person_id)"
        )
    )
