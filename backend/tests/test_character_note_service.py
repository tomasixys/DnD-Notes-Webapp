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
        characters = CharacterService(db)
        character = characters.create(
            campaign,
            CharacterCreate(person=PersonData(name="Nalia")),
        )
        return campaign, character.person.id, characters

    def test_stage_operations_participate_in_the_outer_transaction(self):
        with Session(self.engine) as db:
            campaign, person_id, characters = self._create_character(db)
            character_notes = CharacterNoteService(db, characters)
            backstory_notes = BackstoryNoteService(db, characters)

            note = character_notes.stage_create(
                campaign,
                person_id,
                CharacterNoteData(title="Plan", tags=["urgent"]),
            )
            backstory = backstory_notes.stage_create(
                campaign,
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
            campaign, person_id, characters = self._create_character(db)
            character_notes = CharacterNoteService(db, characters)
            backstory_notes = BackstoryNoteService(db, characters)

            note = character_notes.create(
                campaign,
                person_id,
                CharacterNoteData(title="Plan", tags=["urgent"]),
            )
            backstory = backstory_notes.create(
                campaign,
                person_id,
                CharacterNoteData(title="Family", tags=["childhood"]),
            )

            updated = character_notes.update(
                campaign,
                person_id,
                note.id,
                CharacterNoteData(title="New plan", tags=["revised"]),
            )
            character_notes.delete(campaign, person_id, note.id)

            self.assertEqual("New plan", updated.title)
            self.assertIsNone(db.get(CharacterNote, note.id))
            self.assertIsNotNone(db.get(BackstoryNote, backstory.id))
            remaining_assignments = db.exec(select(TagAssignment)).all()
            self.assertEqual(1, len(remaining_assignments))
            self.assertEqual(
                ResourceType.BACKSTORY_NOTE.value,
                remaining_assignments[0].owner_type,
            )


if __name__ == "__main__":
    unittest.main()
