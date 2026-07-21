"""Migration from schema version 1 to schema version 2."""

from sqlalchemy import inspect, text

from app.tags import normalize_tag_label


REFERENCE_LABEL_COLUMNS = {
    "session": ("sessionnote", "title"),
    "person": ("person", "name"),
    "location": ("location", "name"),
    "faction": ("faction", "name"),
}


def _canonicalize_resolved_tags(connection) -> None:
    """Merge v1 aliases that resolve to the same resource identity."""
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

    assignment_columns = {
        column["name"]
        for column in inspect(connection).get_columns("tagassignment")
    }
    has_relationship_type = "relationship_type" in assignment_columns

    for destination, identity_key, duplicates, canonical_label in destinations:
        for duplicate in duplicates:
            parameters = {
                "destination_id": destination["id"],
                "source_id": duplicate["id"],
            }
            if has_relationship_type:
                connection.execute(
                    text(
                        "INSERT OR IGNORE INTO tagassignment "
                        "(tag_id, owner_type, owner_id, relationship_type) "
                        "SELECT :destination_id, owner_type, owner_id, "
                        "relationship_type FROM tagassignment "
                        "WHERE tag_id = :source_id"
                    ),
                    parameters,
                )
            else:
                connection.execute(
                    text(
                        "INSERT OR IGNORE INTO tagassignment "
                        "(tag_id, owner_type, owner_id) "
                        "SELECT :destination_id, owner_type, owner_id "
                        "FROM tagassignment WHERE tag_id = :source_id"
                    ),
                    parameters,
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


def _rebuild_tag_assignments(connection) -> None:
    """Replace the v1 assignment table with the final v2 relationship schema."""
    columns = {
        column["name"]
        for column in inspect(connection).get_columns("tagassignment")
    }
    relationship_expression = (
        "COALESCE(relationship_type, 'associated_with')"
        if "relationship_type" in columns
        else "'associated_with'"
    )

    connection.execute(text("DROP TABLE IF EXISTS tagassignment_v2"))
    connection.execute(
        text(
            "CREATE TABLE tagassignment_v2 ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "tag_id INTEGER NOT NULL, "
            "owner_type VARCHAR NOT NULL, "
            "owner_id INTEGER NOT NULL, "
            "relationship_type VARCHAR NOT NULL, "
            "CONSTRAINT uq_tag_assignment_owner_relationship UNIQUE "
            "(tag_id, owner_type, owner_id, relationship_type), "
            "FOREIGN KEY(tag_id) REFERENCES tag (id) ON DELETE CASCADE"
            ")"
        )
    )
    connection.execute(
        text(
            "INSERT INTO tagassignment_v2 "
            "(id, tag_id, owner_type, owner_id, relationship_type) "
            "SELECT id, tag_id, owner_type, owner_id, "
            f"{relationship_expression} FROM tagassignment"
        )
    )
    connection.execute(text("DROP TABLE tagassignment"))
    connection.execute(
        text("ALTER TABLE tagassignment_v2 RENAME TO tagassignment")
    )
    connection.execute(
        text("CREATE INDEX ix_tagassignment_tag_id ON tagassignment (tag_id)")
    )
    connection.execute(
        text(
            "CREATE INDEX ix_tagassignment_owner_type "
            "ON tagassignment (owner_type)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX ix_tagassignment_owner_id "
            "ON tagassignment (owner_id)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX ix_tagassignment_relationship_type "
            "ON tagassignment (relationship_type)"
        )
    )


def _strip_reference_prefix(value: str, reference_type: str) -> str:
    cleaned = " ".join(value.strip().split())
    prefix, separator, remainder = cleaned.partition(":")
    if (
        separator
        and prefix.strip().casefold() == reference_type
        and remainder.strip()
    ):
        return " ".join(remainder.strip().split())
    return cleaned


def _migrate_relationship_field(
    connection,
    owner_table: str,
    owner_type: str,
    field_name: str,
    reference_table: str,
    reference_type: str,
    relationship_type: str,
) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    if owner_table not in existing_tables or reference_table not in existing_tables:
        return
    owner_columns = {
        column["name"]
        for column in inspector.get_columns(owner_table)
    }
    if field_name not in owner_columns:
        return

    targets_by_name: dict[tuple[int, str], list[dict]] = {}
    target_rows = connection.execute(
        text(f'SELECT id, campaign_id, name FROM "{reference_table}"')
    ).mappings().all()
    for target in target_rows:
        key = (
            target["campaign_id"],
            normalize_tag_label(target["name"]),
        )
        targets_by_name.setdefault(key, []).append(target)

    owner_rows = connection.execute(
        text(
            f'SELECT id, campaign_id, "{field_name}" AS reference_label '
            f'FROM "{owner_table}" '
            f'WHERE "{field_name}" IS NOT NULL '
            f'AND TRIM("{field_name}") != \'\''
        )
    ).mappings().all()

    for owner in owner_rows:
        label = _strip_reference_prefix(
            str(owner["reference_label"]),
            reference_type,
        )
        normalized_label = normalize_tag_label(label)
        matches = targets_by_name.get(
            (owner["campaign_id"], normalized_label),
            [],
        )

        if len(matches) == 1:
            target = matches[0]
            tag_key = f"reference:{reference_type}:{target['id']}"
            tag_label = target["name"]
            reference_id = target["id"]
            resolution_state = "resolved"
        else:
            tag_key = f"{reference_type}:{normalized_label}"
            tag_label = label
            reference_id = None
            resolution_state = "ambiguous" if len(matches) > 1 else "unresolved"

        connection.execute(
            text(
                "INSERT OR IGNORE INTO tag "
                "(campaign_id, label, normalized_label, key, "
                "reference_type, reference_id, resolution_state) "
                "VALUES (:campaign_id, :label, :normalized_label, :key, "
                ":reference_type, :reference_id, :resolution_state)"
            ),
            {
                "campaign_id": owner["campaign_id"],
                "label": tag_label,
                "normalized_label": normalize_tag_label(tag_label),
                "key": tag_key,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "resolution_state": resolution_state,
            },
        )
        tag_id = connection.execute(
            text(
                "SELECT id FROM tag "
                "WHERE campaign_id = :campaign_id AND key = :key"
            ),
            {"campaign_id": owner["campaign_id"], "key": tag_key},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT OR IGNORE INTO tagassignment "
                "(tag_id, owner_type, owner_id, relationship_type) "
                "VALUES (:tag_id, :owner_type, :owner_id, "
                ":relationship_type)"
            ),
            {
                "tag_id": tag_id,
                "owner_type": owner_type,
                "owner_id": owner["id"],
                "relationship_type": relationship_type,
            },
        )


def _migrate_plain_relationship_fields(connection) -> None:
    relationships = [
        ("person", "person", "faction", "faction", "faction", "member_of"),
        ("person", "person", "location", "location", "location", "located_in"),
        ("location", "location", "parent_location", "location", "location", "part_of"),
        ("faction", "faction", "location", "location", "location", "based_in"),
    ]
    for relationship in relationships:
        _migrate_relationship_field(connection, *relationship)


def _drop_obsolete_resource_fields(connection) -> None:
    legacy_columns = {
        "sessionnote": ("tags",),
        "person": ("tags", "faction", "location"),
        "location": ("tags", "parent_location"),
        "faction": ("tags", "location"),
    }
    existing_tables = set(inspect(connection).get_table_names())

    for table_name, column_names in legacy_columns.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {
            column["name"]
            for column in inspect(connection).get_columns(table_name)
        }
        for column_name in column_names:
            if column_name not in existing_columns:
                continue
            connection.execute(
                text(
                    f'ALTER TABLE "{table_name}" '
                    f'DROP COLUMN "{column_name}"'
                )
            )
            existing_columns.remove(column_name)


def migrate_to_v2(connection) -> None:
    _canonicalize_resolved_tags(connection)
    _rebuild_tag_assignments(connection)
    _migrate_plain_relationship_fields(connection)
    _drop_obsolete_resource_fields(connection)
