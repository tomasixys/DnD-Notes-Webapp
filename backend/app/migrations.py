import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy import Engine, inspect, text

from app.tag_handler import normalize_tag_label


CURRENT_DATABASE_VERSION = 1

LEGACY_TAG_TABLES = {
    "sessionnote": "session",
    "person": "person",
    "location": "location",
    "faction": "faction",
}


def get_database_version(database_path: Path) -> int:
    if not database_path.exists():
        return 0

    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0


def backup_database_before_migration(database_path: Path) -> Path | None:
    if (
        not database_path.exists()
        or get_database_version(database_path) >= CURRENT_DATABASE_VERSION
    ):
        return None

    backup_path = database_path.with_name(
        f"{database_path.name}.pre-v{CURRENT_DATABASE_VERSION}.bak"
    )
    if not backup_path.exists():
        shutil.copy2(database_path, backup_path)
    return backup_path


def _decode_legacy_tags(raw_tags) -> list[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, list):
        return [str(tag) for tag in raw_tags]

    try:
        decoded = json.loads(raw_tags)
    except (TypeError, json.JSONDecodeError):
        return []

    return [str(tag) for tag in decoded] if isinstance(decoded, list) else []


def migrate_legacy_json_tags(connection) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    for table_name, owner_type in LEGACY_TAG_TABLES.items():
        if table_name not in existing_tables:
            continue

        columns = {
            column["name"]
            for column in inspector.get_columns(table_name)
        }
        if "tags" not in columns:
            continue

        rows = connection.execute(
            text(
                f'SELECT id, campaign_id, tags FROM "{table_name}" '
                "WHERE tags IS NOT NULL"
            )
        ).mappings()

        for row in rows:
            seen_keys: set[str] = set()
            for raw_tag in _decode_legacy_tags(row["tags"]):
                label = " ".join(raw_tag.strip().split())
                normalized_label = normalize_tag_label(label)
                if not normalized_label:
                    continue

                # Existing tags predate typed references, so they are migrated
                # conservatively as passive tags rather than reinterpreted.
                key = f"passive:{normalized_label}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                connection.execute(
                    text(
                        "INSERT OR IGNORE INTO tag "
                        "(campaign_id, label, normalized_label, key, "
                        "reference_type, reference_id, resolution_state) "
                        "VALUES (:campaign_id, :label, :normalized_label, :key, "
                        "NULL, NULL, 'passive')"
                    ),
                    {
                        "campaign_id": row["campaign_id"],
                        "label": label,
                        "normalized_label": normalized_label,
                        "key": key,
                    },
                )
                tag_id = connection.execute(
                    text(
                        "SELECT id FROM tag "
                        "WHERE campaign_id = :campaign_id AND key = :key"
                    ),
                    {"campaign_id": row["campaign_id"], "key": key},
                ).scalar_one()
                connection.execute(
                    text(
                        "INSERT OR IGNORE INTO tagassignment "
                        "(tag_id, owner_type, owner_id) "
                        "VALUES (:tag_id, :owner_type, :owner_id)"
                    ),
                    {
                        "tag_id": tag_id,
                        "owner_type": owner_type,
                        "owner_id": row["id"],
                    },
                )


def run_database_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        version = int(
            connection.execute(text("PRAGMA user_version")).scalar_one()
        )

        if version < 1:
            migrate_legacy_json_tags(connection)
            connection.execute(text("PRAGMA user_version = 1"))

        if version > CURRENT_DATABASE_VERSION:
            raise RuntimeError(
                "Database was created by a newer version of Campaign Notes"
            )
