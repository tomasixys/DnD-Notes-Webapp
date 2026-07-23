import unittest

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.api import RollCreate, SessionNoteData
from app.models.database import (
    Campaign,
    RollEntry,
    SessionNote,
    TagAssignment,
)
from app.services.campaign_context import CampaignContext
from app.services.rolls import RollService
from app.services.sessions import SessionNoteService


class SessionAndRollServiceTests(unittest.TestCase):
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

    @staticmethod
    def _create_campaign(db: Session, name: str = "Test") -> Campaign:
        campaign = Campaign(name=name)
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    def test_staged_session_and_rolls_share_the_outer_transaction(self):
        with Session(self.engine) as db:
            campaign = self._create_campaign(db)
            context = CampaignContext(db, campaign)
            sessions = SessionNoteService(context)

            session_note = sessions.stage_create(
                SessionNoteData(
                    date="2026-07-23",
                    title="Arrival",
                    session_number=1,
                    tags=["city"],
                ),
            )
            roll = sessions.rolls.stage_create(
                RollCreate(session_id=session_note.id, roll=18),
            )
            session_note_id = session_note.id
            roll_id = roll.id

            self.assertIsNotNone(db.get(SessionNote, session_note_id))
            self.assertIsNotNone(db.get(RollEntry, roll_id))
            self.assertEqual(1, len(db.exec(select(TagAssignment)).all()))

            db.rollback()

            self.assertIsNone(db.get(SessionNote, session_note_id))
            self.assertIsNone(db.get(RollEntry, roll_id))
            self.assertEqual([], db.exec(select(TagAssignment)).all())

    def test_standalone_services_commit_mutations_and_statistics(self):
        with Session(self.engine) as db:
            campaign = self._create_campaign(db)
            context = CampaignContext(db, campaign)
            sessions = SessionNoteService(context)
            created = sessions.create(
                SessionNoteData(
                    date="2026-07-23",
                    title="Arrival",
                    session_number=1,
                ),
            )
            session_note_id = created.id
            rolls = RollService(context)

            rolls.create(
                RollCreate(session_id=session_note_id, roll=20),
            )
            response = rolls.create(
                RollCreate(session_id=session_note_id, roll=1),
            )

            self.assertEqual(2, response.campaign_stats.num_rolls)
            self.assertEqual(10.5, response.session_stats.average)

            updated = sessions.update(
                session_note_id,
                SessionNoteData(
                    date="2026-07-24",
                    title="The City",
                    session_number=2,
                ),
            )
            self.assertEqual(2, updated.session_number)

            deleted_rolls = rolls.delete_for_session(session_note_id)
            self.assertEqual(
                0,
                deleted_rolls.campaign_stats.num_rolls,
            )
            self.assertEqual(
                [],
                deleted_rolls.session_stats.rolls,
            )
            self.assertEqual([], db.exec(select(RollEntry)).all())
            self.assertIsNotNone(db.get(SessionNote, session_note_id))

            deleted_session = sessions.delete(session_note_id)
            self.assertEqual(
                session_note_id,
                deleted_session.deleted_id,
            )
            self.assertIsNone(db.get(SessionNote, session_note_id))

    def test_roll_mutations_reject_a_session_from_another_campaign(self):
        with Session(self.engine) as db:
            first_campaign = self._create_campaign(db, "First")
            second_campaign = self._create_campaign(db, "Second")
            first_context = CampaignContext(db, first_campaign)
            session_note = SessionNoteService(first_context).create(
                SessionNoteData(
                    date="2026-07-23",
                    title="Arrival",
                    session_number=1,
                ),
            )

            with self.assertRaises(HTTPException) as context:
                RollService(
                    CampaignContext(db, second_campaign)
                ).create(
                    RollCreate(session_id=session_note.id, roll=10),
                )

            self.assertEqual(404, context.exception.status_code)
            self.assertEqual([], db.exec(select(RollEntry)).all())


if __name__ == "__main__":
    unittest.main()
