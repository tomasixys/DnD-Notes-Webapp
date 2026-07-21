import asyncio
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile
from sqlalchemy import event, inspect
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.migrations import CURRENT_DATABASE_VERSION, run_database_migrations
from app.models.api import (
    CharacterCreate,
    CharacterNoteData,
    PersonData,
    SessionNoteData,
)
from app.models.database import (
    BackstoryNote,
    Campaign,
    CharacterNote,
    CharacterProfile,
    NoteBase,
    Person,
    SessionNote,
    TagAssignment,
)
from app.models.enums import ResourceType
from app.routers.characters import (
    create_backstory_note,
    create_character,
    create_character_note,
    delete_character,
    get_active_character,
    get_backstory_notes,
    get_character,
    get_character_notes,
)
from app.routers.people import delete_person, person_to_read
from app.routers.sessions import create_session_note
from app.routers.campaigns import (
    export_campaign_backup,
    import_campaign_backup,
)


class CharacterApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_replacement_character_changes_pointer_without_losing_history(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            first = create_character(
                campaign.id,
                CharacterCreate(
                    person=PersonData(name="Nalia", role="Wizard"),
                    short_bio="Academy exile",
                ),
                db,
            )
            second = create_character(
                campaign.id,
                CharacterCreate(
                    person=PersonData(name="Sable", role="Rogue"),
                    short_bio="Replacement character",
                ),
                db,
            )

            db.refresh(campaign)
            self.assertEqual(
                campaign.active_character_person_id,
                second.person.id,
            )
            former = get_character(campaign.id, first.person.id, db)
            self.assertFalse(former.is_active)
            self.assertTrue(second.is_active)
            self.assertIsNotNone(db.get(CharacterProfile, first.person.id))
            self.assertIsNotNone(db.get(Person, first.person.id))
            self.assertEqual(len(db.exec(select(CharacterProfile)).all()), 2)

            active = get_active_character(campaign.id, db)
            self.assertEqual(active.person.id, second.person.id)

            former_person = person_to_read(
                db.get(Person, first.person.id), db
            )
            self.assertTrue(former_person.character_profile_available)
            self.assertFalse(former_person.is_active_character)

    def test_all_note_models_share_note_base_and_sessions_keep_api_shape(self):
        self.assertTrue(issubclass(SessionNote, NoteBase))
        self.assertTrue(issubclass(CharacterNote, NoteBase))
        self.assertTrue(issubclass(BackstoryNote, NoteBase))

        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            response = create_session_note(
                campaign.id,
                SessionNoteData(
                    date="2026-07-21",
                    title="Arrival",
                    description="Reached the city",
                    session_number=1,
                ),
                db,
            )
            stored = db.get(SessionNote, response.id)

            self.assertEqual(stored.content, "Reached the city")
            self.assertEqual(response.description, "Reached the city")

    def test_notes_and_backstory_share_crud_shape_and_keep_separate_types(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            person = Person(campaign_id=0, name="Nalia")
            db.add(campaign)
            db.flush()
            person.campaign_id = campaign.id
            db.add(person)
            db.commit()
            db.refresh(campaign)
            db.refresh(person)

            create_character(
                campaign.id,
                CharacterCreate(person_id=person.id),
                db,
            )
            note = create_character_note(
                campaign.id,
                person.id,
                CharacterNoteData(
                    title="Shopping list",
                    content="Healing potion",
                    tags=["shopping", "person:Nalia"],
                ),
                db,
            )
            backstory = create_backstory_note(
                campaign.id,
                person.id,
                CharacterNoteData(
                    title="Family",
                    content="Raised by an aunt",
                    tags=["family"],
                ),
                db,
            )

            self.assertEqual(
                {tag.value for tag in note.tags},
                {"shopping", "person:Nalia"},
            )
            self.assertEqual([tag.value for tag in backstory.tags], ["family"])

            notes = get_character_notes(
                campaign.id,
                person.id,
                db,
            )
            backstories = get_backstory_notes(
                campaign.id,
                person.id,
                db,
            )
            self.assertEqual([entry.id for entry in notes], [note.id])
            self.assertEqual(
                [entry.id for entry in backstories],
                [backstory.id],
            )

    def test_profile_delete_preserves_person_and_person_delete_cleans_profile(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            character = create_character(
                campaign.id,
                CharacterCreate(person=PersonData(name="Nalia")),
                db,
            )
            entry = create_character_note(
                campaign.id,
                character.person.id,
                CharacterNoteData(
                    title="To do",
                    tags=["urgent"],
                ),
                db,
            )

            delete_character(campaign.id, character.person.id, db)
            self.assertIsNotNone(db.get(Person, character.person.id))
            self.assertIsNone(db.get(CharacterProfile, character.person.id))
            self.assertIsNone(db.get(CharacterNote, entry.id))
            db.refresh(campaign)
            self.assertIsNone(campaign.active_character_person_id)
            self.assertEqual(
                db.exec(
                    select(TagAssignment).where(
                        TagAssignment.owner_type
                        == ResourceType.CHARACTER_NOTE.value
                    )
                ).all(),
                [],
            )

            replacement = create_character(
                campaign.id,
                CharacterCreate(person=PersonData(name="Sable")),
                db,
            )
            create_backstory_note(
                campaign.id,
                replacement.person.id,
                CharacterNoteData(
                    title="Earlier work",
                ),
                db,
            )
            delete_person(campaign.id, replacement.person.id, db)
            self.assertIsNone(db.get(Person, replacement.person.id))
            self.assertIsNone(db.get(CharacterProfile, replacement.person.id))
            db.refresh(campaign)
            self.assertIsNone(campaign.active_character_person_id)

    def test_campaign_backup_round_trips_character_profiles_and_entries(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "campaign.backup"
            with Session(self.engine) as db:
                campaign = Campaign(name="Test")
                db.add(campaign)
                db.commit()
                db.refresh(campaign)

                character = create_character(
                    campaign.id,
                    CharacterCreate(
                        person=PersonData(name="Nalia"),
                        short_bio="Academy exile",
                        appearance="Silver hair",
                    ),
                    db,
                )
                create_backstory_note(
                    campaign.id,
                    character.person.id,
                    CharacterNoteData(
                        title="Family",
                        content="Raised by an aunt",
                        tags=["family"],
                    ),
                    db,
                )

                with patch(
                    "app.routers.campaigns.make_backup_archive_path",
                    return_value=(archive_path, "campaign.backup"),
                ):
                    export_campaign_backup(campaign.id, db)

                upload = UploadFile(
                    file=io.BytesIO(archive_path.read_bytes()),
                    filename="campaign.backup",
                )
                imported_response = asyncio.run(
                    import_campaign_backup(upload, db)
                )
                imported_campaign = db.get(
                    Campaign, imported_response["id"]
                )
                imported_profile = db.get(
                    CharacterProfile,
                    imported_campaign.active_character_person_id,
                )
                imported_entries = db.exec(
                    select(BackstoryNote).where(
                        BackstoryNote.character_person_id
                        == imported_profile.person_id
                    )
                ).all()

                self.assertEqual(imported_profile.short_bio, "Academy exile")
                self.assertEqual(imported_profile.appearance, "Silver hair")
                self.assertEqual(len(imported_entries), 1)
                self.assertEqual(imported_entries[0].title, "Family")
class CharacterMigrationTests(unittest.TestCase):
    def test_v3_migration_adds_character_schema_to_version_two_database(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "version-two.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE campaign (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE person ("
                    "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, "
                    "name TEXT NOT NULL)"
                )
                connection.execute("PRAGMA user_version = 2")
                connection.commit()

            engine = create_engine(
                f"sqlite:///{database_path}",
                poolclass=NullPool,
            )
            run_database_migrations(engine)

            schema = inspect(engine)
            campaign_columns = {
                column["name"] for column in schema.get_columns("campaign")
            }
            table_names = set(schema.get_table_names())
            with engine.connect() as connection:
                version = connection.exec_driver_sql(
                    "PRAGMA user_version"
                ).scalar_one()
            engine.dispose()

            self.assertEqual(version, CURRENT_DATABASE_VERSION)
            self.assertIn("active_character_person_id", campaign_columns)
            self.assertIn("characterprofile", table_names)
            self.assertIn("characternote", table_names)
            self.assertIn("backstorynote", table_names)

    def test_v3_migration_splits_legacy_character_entries_and_tags(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "character-entry.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE campaign (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE person (
                        id INTEGER PRIMARY KEY,
                        campaign_id INTEGER NOT NULL,
                        name TEXT NOT NULL
                    );
                    CREATE TABLE characterprofile (
                        person_id INTEGER PRIMARY KEY,
                        short_bio TEXT NOT NULL DEFAULT '',
                        appearance TEXT NOT NULL DEFAULT '',
                        image_path TEXT NOT NULL DEFAULT ''
                    );
                    CREATE TABLE characterentry (
                        id INTEGER PRIMARY KEY,
                        campaign_id INTEGER NOT NULL,
                        character_person_id INTEGER NOT NULL,
                        entry_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    );
                    CREATE TABLE sessionnote (
                        id INTEGER PRIMARY KEY,
                        campaign_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        date TEXT NOT NULL,
                        session_number INTEGER NOT NULL
                    );
                    CREATE TABLE tag (
                        id INTEGER PRIMARY KEY,
                        campaign_id INTEGER NOT NULL,
                        label TEXT NOT NULL,
                        normalized_label TEXT NOT NULL,
                        key TEXT NOT NULL,
                        reference_type TEXT,
                        reference_id INTEGER,
                        resolution_state TEXT NOT NULL,
                        UNIQUE(campaign_id, key)
                    );
                    CREATE TABLE tagassignment (
                        id INTEGER PRIMARY KEY,
                        tag_id INTEGER NOT NULL,
                        owner_type TEXT NOT NULL,
                        owner_id INTEGER NOT NULL,
                        relationship_type TEXT NOT NULL,
                        UNIQUE(tag_id, owner_type, owner_id, relationship_type)
                    );
                    INSERT INTO campaign VALUES (1, 'Test');
                    INSERT INTO person VALUES (5, 1, 'Nalia');
                    INSERT INTO characterprofile VALUES (5, '', '', '');
                    INSERT INTO characterentry VALUES
                        (10, 1, 5, 'NOTE', 'Shopping', 'Potions',
                         '2026-01-01', '2026-01-02'),
                        (11, 1, 5, 'backstory', 'Family', 'An aunt',
                         '2026-01-03', '2026-01-04');
                    INSERT INTO sessionnote VALUES
                        (20, 1, 'Arrival', 'Reached the city', '2026-01-05', 1);
                    INSERT INTO tag VALUES
                        (30, 1, 'shopping', 'shopping', 'passive:shopping',
                         NULL, NULL, 'passive'),
                        (31, 1, 'Family', 'family', 'reference:character_entry:11',
                         'character_entry', 11, 'resolved');
                    INSERT INTO tagassignment VALUES
                        (40, 30, 'character_entry', 10, 'associated_with');
                    PRAGMA user_version = 2;
                    """
                )
                connection.commit()

            engine = create_engine(
                f"sqlite:///{database_path}",
                poolclass=NullPool,
            )
            run_database_migrations(engine)
            with engine.connect() as connection:
                version = connection.exec_driver_sql(
                    "PRAGMA user_version"
                ).scalar_one()
                note_rows = connection.exec_driver_sql(
                    "SELECT id, title FROM characternote"
                ).all()
                backstory_rows = connection.exec_driver_sql(
                    "SELECT id, title FROM backstorynote"
                ).all()
                assignment = connection.exec_driver_sql(
                    "SELECT owner_type, owner_id FROM tagassignment"
                ).one()
                reference = connection.exec_driver_sql(
                    "SELECT key, reference_type, reference_id FROM tag WHERE id = 31"
                ).one()
                session_content = connection.exec_driver_sql(
                    "SELECT content FROM sessionnote WHERE id = 20"
                ).scalar_one()
                tables = set(inspect(connection).get_table_names())
                session_columns = {
                    column["name"]
                    for column in inspect(connection).get_columns("sessionnote")
                }
            engine.dispose()

            self.assertEqual(version, CURRENT_DATABASE_VERSION)
            self.assertEqual(note_rows, [(10, "Shopping")])
            self.assertEqual(backstory_rows, [(11, "Family")])
            self.assertEqual(assignment, ("character_note", 10))
            self.assertEqual(
                reference,
                ("reference:backstory_note:11", "backstory_note", 11),
            )
            self.assertEqual(session_content, "Reached the city")
            self.assertNotIn("description", session_columns)
            self.assertNotIn("characterentry", tables)


if __name__ == "__main__":
    unittest.main()
