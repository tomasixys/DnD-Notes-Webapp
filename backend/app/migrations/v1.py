"""Migration from an unversioned database to schema version 1."""

import json

from sqlalchemy import inspect, text

from app.tags import normalize_tag_label


LEGACY_TAG_TABLES = {
    "sessionnote": "session",
    "person": "person",
    "location": "location",
    "faction": "faction",
}


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


def migrate_to_v1(connection) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    assignment_columns = {
        column["name"]
        for column in inspector.get_columns("tagassignment")
    }
    has_relationship_type = "relationship_type" in assignment_columns

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

                parameters = {
                    "tag_id": tag_id,
                    "owner_type": owner_type,
                    "owner_id": row["id"],
                }
                if has_relationship_type:
                    connection.execute(
                        text(
                            "INSERT OR IGNORE INTO tagassignment "
                            "(tag_id, owner_type, owner_id, relationship_type) "
                            "VALUES (:tag_id, :owner_type, :owner_id, "
                            "'associated_with')"
                        ),
                        parameters,
                    )
                else:
                    connection.execute(
                        text(
                            "INSERT OR IGNORE INTO tagassignment "
                            "(tag_id, owner_type, owner_id) "
                            "VALUES (:tag_id, :owner_type, :owner_id)"
                        ),
                        parameters,
                    )
