import unittest

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.api import CharacterCreate, CharacterNoteData, PersonData
from app.models.database import (
    BackstoryNote,
    Campaign,
    CharacterNote,
    TagAssignment,
)
from app.models.enums import ResourceType
from app.services.character_notes import (
    BackstoryNoteService,
    CharacterNoteService,
)
from app.services.campaign_context import CampaignContext
from app.services.characters import CharacterService


class CharacterNoteServiceTests(unittest.TestCase):
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

    def _create_character(self, db: Session):
        campaign = Campaign(name="Test")
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        context = CampaignContext(db, campaign)
        characters = CharacterService(context)
        character = characters.create(
            CharacterCreate(person=PersonData(name="Nalia")),
        )
        return context, character.person.id, characters

    def test_stage_operations_participate_in_the_outer_transaction(self):
        with Session(self.engine) as db:
            context, person_id, characters = self._create_character(db)
            character_notes = CharacterNoteService(context, characters)
            backstory_notes = BackstoryNoteService(context, characters)

            note = character_notes.stage_create(
                person_id,
                CharacterNoteData(title="Plan", tags=["urgent"]),
            )
            backstory = backstory_notes.stage_create(
                person_id,
                CharacterNoteData(title="Family", tags=["childhood"]),
            )
            note_id = note.id
            backstory_id = backstory.id

            self.assertIsNotNone(db.get(CharacterNote, note_id))
            self.assertIsNotNone(db.get(BackstoryNote, backstory_id))
            self.assertEqual(2, len(db.exec(select(TagAssignment)).all()))

            db.rollback()

            self.assertIsNone(db.get(CharacterNote, note_id))
            self.assertIsNone(db.get(BackstoryNote, backstory_id))
            self.assertEqual([], db.exec(select(TagAssignment)).all())

    def test_standalone_services_keep_note_types_separate(self):
        with Session(self.engine) as db:
            context, person_id, characters = self._create_character(db)
            character_notes = CharacterNoteService(context, characters)
            backstory_notes = BackstoryNoteService(context, characters)

            note = character_notes.create(
                person_id,
                CharacterNoteData(title="Plan", tags=["urgent"]),
            )
            backstory = backstory_notes.create(
                person_id,
                CharacterNoteData(title="Family", tags=["childhood"]),
            )

            updated = character_notes.update(
                person_id,
                note.id,
                CharacterNoteData(title="New plan", tags=["revised"]),
            )
            character_notes.delete(person_id, note.id)

            self.assertEqual("New plan", updated.title)
            self.assertIsNone(db.get(CharacterNote, note.id))
            self.assertIsNotNone(db.get(BackstoryNote, backstory.id))
            remaining_assignments = db.exec(select(TagAssignment)).all()
            self.assertEqual(1, len(remaining_assignments))
            self.assertEqual(
                ResourceType.BACKSTORY_NOTE.value,
                remaining_assignments[0].owner_type,
            )

    def test_character_backup_list_composes_both_note_services(self):
        with Session(self.engine) as db:
            context, person_id, characters = self._create_character(db)
            CharacterNoteService(context, characters).create(
                person_id,
                CharacterNoteData(title="Plan", tags=["urgent"]),
            )
            BackstoryNoteService(context, characters).create(
                person_id,
                CharacterNoteData(title="Family", tags=["childhood"]),
            )

            backups = characters.list_backup_entries(
                {person_id: "assets/characters/nalia.png"}
            )

            self.assertEqual(1, len(backups))
            self.assertEqual(person_id, backups[0].person_backup_id)
            self.assertEqual(
                "assets/characters/nalia.png",
                backups[0].image_archive_path,
            )
            self.assertEqual(
                ["Plan"],
                [note.title for note in backups[0].notes],
            )
            self.assertEqual(
                ["Family"],
                [note.title for note in backups[0].backstory_notes],
            )


if __name__ == "__main__":
    unittest.main()
