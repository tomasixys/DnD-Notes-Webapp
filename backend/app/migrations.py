import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy import Engine, inspect, text

from app.tag_handler import normalize_tag_label


CURRENT_DATABASE_VERSION = 2

LEGACY_TAG_TABLES = {
    "sessionnote": "session",
    "person": "person",
    "location": "location",
    "faction": "faction",
}

REFERENCE_LABEL_COLUMNS = {
    "session": ("sessionnote", "title"),
    "person": ("person", "name"),
    "location": ("location", "name"),
    "faction": ("faction", "name"),
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


def migrate_resolved_tags_to_identity_keys(connection) -> None:
    existing_tables = set(inspect(connection).get_table_names())
    rows = connection.execute(
        text(
            "SELECT id, campaign_id, key, reference_type, reference_id "
            "FROM tag "
            "WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL "
            "ORDER BY id"
        )
    ).mappings().all()

    groups: dict[tuple[int, str, int], list[dict]] = {}
    for row in rows:
        identity = (
            row["campaign_id"],
            row["reference_type"],
            row["reference_id"],
        )
        groups.setdefault(identity, []).append(row)

    destinations: list[tuple[dict, str, list[dict], str | None]] = []
    for (campaign_id, reference_type, reference_id), group in groups.items():
        identity_key = f"reference:{reference_type}:{reference_id}"
        destination = next(
            (row for row in group if row["key"] == identity_key),
            group[0],
        )
        duplicates = [row for row in group if row["id"] != destination["id"]]
        canonical_label: str | None = None
        label_source = REFERENCE_LABEL_COLUMNS.get(reference_type)
        if label_source is not None and label_source[0] in existing_tables:
            table_name, column_name = label_source
            canonical_label = connection.execute(
                text(
                    f'SELECT "{column_name}" FROM "{table_name}" '
                    "WHERE id = :reference_id AND campaign_id = :campaign_id"
                ),
                {
                    "reference_id": reference_id,
                    "campaign_id": campaign_id,
                },
            ).scalar_one_or_none()

        destinations.append(
            (destination, identity_key, duplicates, canonical_label)
        )

        connection.execute(
            text("UPDATE tag SET key = :key WHERE id = :tag_id"),
            {
                "key": f"__v2_reference__:{destination['id']}",
                "tag_id": destination["id"],
            },
        )

    for destination, identity_key, duplicates, canonical_label in destinations:
        for duplicate in duplicates:
            connection.execute(
                text(
                    "INSERT OR IGNORE INTO tagassignment "
                    "(tag_id, owner_type, owner_id) "
                    "SELECT :destination_id, owner_type, owner_id "
                    "FROM tagassignment WHERE tag_id = :source_id"
                ),
                {
                    "destination_id": destination["id"],
                    "source_id": duplicate["id"],
                },
            )
            connection.execute(
                text("DELETE FROM tagassignment WHERE tag_id = :tag_id"),
                {"tag_id": duplicate["id"]},
            )
            connection.execute(
                text("DELETE FROM tag WHERE id = :tag_id"),
                {"tag_id": duplicate["id"]},
            )

        values = {"key": identity_key, "tag_id": destination["id"]}
        if canonical_label is None:
            connection.execute(
                text("UPDATE tag SET key = :key WHERE id = :tag_id"),
                values,
            )
        else:
            values.update(
                {
                    "label": canonical_label,
                    "normalized_label": normalize_tag_label(canonical_label),
                }
            )
            connection.execute(
                text(
                    "UPDATE tag SET key = :key, label = :label, "
                    "normalized_label = :normalized_label WHERE id = :tag_id"
                ),
                values,
            )


def run_database_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        version = int(
            connection.execute(text("PRAGMA user_version")).scalar_one()
        )

        if version < 1:
            migrate_legacy_json_tags(connection)
            connection.execute(text("PRAGMA user_version = 1"))

        if version < 2:
            migrate_resolved_tags_to_identity_keys(connection)
            connection.execute(text("PRAGMA user_version = 2"))

        if version > CURRENT_DATABASE_VERSION:
            raise RuntimeError(
                "Database was created by a newer version of Campaign Notes"
            )
