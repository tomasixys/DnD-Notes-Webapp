import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sqlalchemy import create_engine as create_sqlalchemy_engine, text
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.migrations import run_database_migrations
from app.models.database import (
    Campaign,
    Location,
    Person,
    Tag,
    TagAssignment,
)
from app.models.enums import (
    RelationshipType,
    ResourceType,
    TagResolutionState,
)
from app.tags import (
    get_resource_tags,
    handle_tags_of_deleted_resource,
    parse_tag,
    resolve_pending_tags_for_resource,
    sync_resource_tags,
)


class TagHandlerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def test_parses_reserved_prefixes_and_keeps_unknown_prefixes_passive(self):
        linked = parse_tag(" location:  Skummende   Seidel ")
        passive = parse_tag("status:neutral")

        self.assertEqual(linked.reference_type, ResourceType.LOCATION)
        self.assertEqual(linked.label, "Skummende Seidel")
        self.assertIsNone(passive.reference_type)
        self.assertEqual(passive.label, "status:neutral")

    def test_resources_subscribe_to_shared_resolved_tags(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.flush()

            location = Location(campaign_id=campaign.id, name="Skummende Seidel")
            first_person = Person(campaign_id=campaign.id, name="Nalia")
            second_person = Person(campaign_id=campaign.id, name="Sodalan")
            db.add(location)
            db.add(first_person)
            db.add(second_person)
            db.flush()

            raw_tags = ["location:Skummende Seidel", "Neutral"]
            sync_resource_tags(
                db, campaign.id, ResourceType.PERSON, first_person.id, raw_tags
            )
            sync_resource_tags(
                db, campaign.id, ResourceType.PERSON, second_person.id, raw_tags
            )
            db.commit()

            reference_tag = db.exec(
                select(Tag).where(Tag.reference_type == ResourceType.LOCATION.value)
            ).one()
            assignments = db.exec(
                select(TagAssignment).where(
                    TagAssignment.tag_id == reference_tag.id
                )
            ).all()

            self.assertEqual(reference_tag.reference_id, location.id)
            self.assertEqual(
                reference_tag.resolution_state,
                TagResolutionState.RESOLVED.value,
            )
            self.assertEqual(len(assignments), 2)
            self.assertTrue(
                all(
                    assignment.relationship_type
                    == RelationshipType.ASSOCIATED_WITH.value
                    for assignment in assignments
                )
            )
            self.assertEqual(
                get_resource_tags(db, ResourceType.PERSON, first_person.id),
                ["Neutral", "location:Skummende Seidel"],
            )

    def test_unresolved_tag_resolves_when_target_is_created_and_unlinks_on_delete(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            person = Person(campaign_id=0, name="Nalia")
            db.add(campaign)
            db.flush()
            person.campaign_id = campaign.id
            db.add(person)
            db.flush()

            sync_resource_tags(
                db,
                campaign.id,
                ResourceType.PERSON,
                person.id,
                ["location:Missing Inn"],
            )
            tag = db.exec(select(Tag)).one()
            self.assertEqual(tag.resolution_state, "unresolved")

            location = Location(campaign_id=campaign.id, name="Missing Inn")
            db.add(location)
            db.flush()
            resolve_pending_tags_for_resource(
                db, campaign.id, ResourceType.LOCATION, location.name
            )
            db.flush()
            db.refresh(tag)
            self.assertEqual(tag.reference_id, location.id)

            handle_tags_of_deleted_resource(db, ResourceType.LOCATION, location.id)
            db.delete(location)
            db.flush()
            db.refresh(tag)
            self.assertIsNone(tag.reference_id)
            self.assertEqual(tag.resolution_state, "unresolved")


class TagMigrationTests(unittest.TestCase):
    def test_fresh_database_uses_current_schema_version(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "fresh.db"
            engine = create_sqlalchemy_engine(
                f"sqlite:///{database_path}",
                poolclass=NullPool,
            )
            SQLModel.metadata.create_all(engine)

            run_database_migrations(engine)

            with engine.connect() as connection:
                version = connection.execute(
                    text("PRAGMA user_version")
                ).scalar_one()
                assignment_columns = {
                    row[1]
                    for row in connection.execute(
                        text("PRAGMA table_info(tagassignment)")
                    )
                }

            engine.dispose()

            self.assertEqual(version, 2)
            self.assertIn("relationship_type", assignment_columns)

    def test_migrates_legacy_json_tags_as_shared_passive_tags(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "legacy.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE campaign (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE person ("
                    "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, "
                    "tags JSON)"
                )
                connection.execute(
                    "INSERT INTO campaign (id, name) VALUES (1, 'Test')"
                )
                connection.execute(
                    "INSERT INTO person (id, campaign_id, tags) VALUES (?, ?, ?)",
                    (3, 1, json.dumps(["Neutral", "Neutral", "Ally"])),
                )
                connection.commit()

            engine = create_sqlalchemy_engine(
                f"sqlite:///{database_path}",
                poolclass=NullPool,
            )
            Tag.__table__.create(engine)
            TagAssignment.__table__.create(engine)
            run_database_migrations(engine)

            with engine.connect() as connection:
                tags = connection.execute(
                    text("SELECT label, resolution_state FROM tag ORDER BY label")
                ).all()
                assignments = connection.execute(
                    text(
                        "SELECT owner_type, owner_id, relationship_type "
                        "FROM tagassignment"
                    )
                ).all()
                version = connection.execute(text("PRAGMA user_version")).scalar_one()

            engine.dispose()

            self.assertEqual(tags, [("Ally", "passive"), ("Neutral", "passive")])
            self.assertEqual(
                assignments,
                [
                    ("person", 3, "associated_with"),
                    ("person", 3, "associated_with"),
                ],
            )
            self.assertEqual(version, 2)

    def test_migrates_resolved_aliases_to_one_identity_tag(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "version-one.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE tag ("
                    "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, "
                    "label TEXT NOT NULL, normalized_label TEXT NOT NULL, "
                    "key TEXT NOT NULL, reference_type TEXT, reference_id INTEGER, "
                    "resolution_state TEXT NOT NULL, UNIQUE(campaign_id, key))"
                )
                connection.execute(
                    "CREATE TABLE tagassignment ("
                    "id INTEGER PRIMARY KEY, tag_id INTEGER NOT NULL, "
                    "owner_type TEXT NOT NULL, owner_id INTEGER NOT NULL, "
                    "UNIQUE(tag_id, owner_type, owner_id))"
                )
                connection.execute(
                    "CREATE TABLE location ("
                    "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, "
                    "name TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO location VALUES (9, 4, 'New Harbor')"
                )
                connection.execute(
                    "INSERT INTO tag VALUES "
                    "(1, 4, 'Old Harbor', 'old harbor', 'location:old harbor', "
                    "'location', 9, 'resolved')"
                )
                connection.execute(
                    "INSERT INTO tag VALUES "
                    "(2, 4, 'Harbor', 'harbor', 'location:harbor', "
                    "'location', 9, 'resolved')"
                )
                connection.execute(
                    "INSERT INTO tagassignment VALUES (1, 1, 'person', 10)"
                )
                connection.execute(
                    "INSERT INTO tagassignment VALUES (2, 2, 'person', 11)"
                )
                connection.execute("PRAGMA user_version = 1")
                connection.commit()

            engine = create_sqlalchemy_engine(
                f"sqlite:///{database_path}",
                poolclass=NullPool,
            )
            run_database_migrations(engine)

            with engine.connect() as connection:
                tags = connection.execute(
                    text(
                        "SELECT key, label, normalized_label, reference_id "
                        "FROM tag"
                    )
                ).all()
                assignments = connection.execute(
                    text(
                        "SELECT tag_id, owner_type, owner_id, relationship_type "
                        "FROM tagassignment ORDER BY owner_id"
                    )
                ).all()
                version = connection.execute(text("PRAGMA user_version")).scalar_one()

            engine.dispose()

            self.assertEqual(
                tags,
                [("reference:location:9", "New Harbor", "new harbor", 9)],
            )
            self.assertEqual(
                assignments,
                [
                    (1, "person", 10, "associated_with"),
                    (1, "person", 11, "associated_with"),
                ],
            )
            self.assertEqual(version, 2)

    def test_migrates_plain_relationship_fields_to_typed_assignments(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "version-one.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE tag ("
                    "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, "
                    "label TEXT NOT NULL, normalized_label TEXT NOT NULL, "
                    "key TEXT NOT NULL, reference_type TEXT, reference_id INTEGER, "
                    "resolution_state TEXT NOT NULL, UNIQUE(campaign_id, key))"
                )
                connection.execute(
                    "CREATE TABLE tagassignment ("
                    "id INTEGER PRIMARY KEY, tag_id INTEGER NOT NULL, "
                    "owner_type TEXT NOT NULL, owner_id INTEGER NOT NULL, "
                    "UNIQUE(tag_id, owner_type, owner_id))"
                )
                connection.execute(
                    "CREATE TABLE location ("
                    "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, "
                    "name TEXT NOT NULL, parent_location TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE faction ("
                    "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, "
                    "name TEXT NOT NULL, location TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE person ("
                    "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, "
                    "name TEXT NOT NULL, faction TEXT NOT NULL, "
                    "location TEXT NOT NULL)"
                )
                connection.executemany(
                    "INSERT INTO location VALUES (?, 1, ?, ?)",
                    [(10, "Gernanti", ""), (11, "Academy", "location:Gernanti")],
                )
                connection.execute(
                    "INSERT INTO faction VALUES (20, 1, 'Dragon Order', 'Academy')"
                )
                connection.execute(
                    "INSERT INTO person VALUES "
                    "(30, 1, 'Nalia', 'faction:Dragon Order', 'Academy')"
                )
                connection.execute("PRAGMA user_version = 1")
                connection.commit()

            engine = create_sqlalchemy_engine(
                f"sqlite:///{database_path}",
                poolclass=NullPool,
            )
            run_database_migrations(engine)

            with engine.connect() as connection:
                assignments = connection.execute(
                    text(
                        "SELECT ta.owner_type, ta.owner_id, "
                        "ta.relationship_type, t.reference_type, t.reference_id "
                        "FROM tagassignment ta JOIN tag t ON t.id = ta.tag_id "
                        "ORDER BY ta.owner_type, ta.owner_id, ta.relationship_type"
                    )
                ).all()
                person_columns = {
                    row[1]
                    for row in connection.execute(text("PRAGMA table_info(person)"))
                }
                location_columns = {
                    row[1]
                    for row in connection.execute(text("PRAGMA table_info(location)"))
                }
                faction_columns = {
                    row[1]
                    for row in connection.execute(text("PRAGMA table_info(faction)"))
                }
                version = connection.execute(text("PRAGMA user_version")).scalar_one()

            engine.dispose()

            self.assertEqual(
                assignments,
                [
                    ("faction", 20, "based_in", "location", 11),
                    ("location", 11, "part_of", "location", 10),
                    ("person", 30, "located_in", "location", 11),
                    ("person", 30, "member_of", "faction", 20),
                ],
            )
            self.assertNotIn("faction", person_columns)
            self.assertNotIn("location", person_columns)
            self.assertNotIn("tags", person_columns)
            self.assertNotIn("parent_location", location_columns)
            self.assertNotIn("tags", location_columns)
            self.assertNotIn("location", faction_columns)
            self.assertNotIn("tags", faction_columns)
            self.assertEqual(version, 2)


if __name__ == "__main__":
    unittest.main()
