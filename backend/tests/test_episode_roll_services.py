import unittest

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.api import EpisodeData, RollCreate
from app.models.database import (
    Campaign,
    Episode,
    RollEntry,
    TagAssignment,
)
from app.models.enums import ResourceType
from app.authorization.context import CampaignContext
from tests.authorization_helpers import campaign_context
from app.services.episodes import EpisodeService
from app.services.rolls import RollService


class EpisodeAndRollServiceTests(unittest.TestCase):
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

    def test_episode_names_preserve_storage_and_wire_compatibility(self):
        self.assertEqual("sessionnote", Episode.__tablename__)
        self.assertEqual("session", ResourceType.EPISODE.value)

    @staticmethod
    def _create_campaign(db: Session, name: str = "Test") -> Campaign:
        campaign = Campaign(name=name)
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    def test_staged_episode_and_rolls_share_the_outer_transaction(self):
        with Session(self.engine) as db:
            campaign = self._create_campaign(db)
            context = campaign_context(db, campaign)
            episodes = EpisodeService(context)

            episode = episodes.stage_create(
                EpisodeData(
                    date="2026-07-23",
                    title="Arrival",
                    session_number=1,
                    tags=["city"],
                ),
            )
            roll = episodes.rolls.stage_create(
                RollCreate(session_id=episode.id, roll=18),
            )
            episode_id = episode.id
            roll_id = roll.id

            self.assertIsNotNone(db.get(Episode, episode_id))
            self.assertIsNotNone(db.get(RollEntry, roll_id))
            self.assertEqual(1, len(db.exec(select(TagAssignment)).all()))

            db.rollback()

            self.assertIsNone(db.get(Episode, episode_id))
            self.assertIsNone(db.get(RollEntry, roll_id))
            self.assertEqual([], db.exec(select(TagAssignment)).all())

    def test_standalone_services_commit_mutations_and_statistics(self):
        with Session(self.engine) as db:
            campaign = self._create_campaign(db)
            context = campaign_context(db, campaign)
            episodes = EpisodeService(context)
            created = episodes.create(
                EpisodeData(
                    date="2026-07-23",
                    title="Arrival",
                    session_number=1,
                ),
            )
            episode_id = created.id
            rolls = RollService(context)

            rolls.create(
                RollCreate(session_id=episode_id, roll=20),
            )
            response = rolls.create(
                RollCreate(session_id=episode_id, roll=1),
            )

            self.assertEqual(2, response.campaign_stats.num_rolls)
            self.assertEqual(10.5, response.session_stats.average)

            updated = episodes.update(
                episode_id,
                EpisodeData(
                    date="2026-07-24",
                    title="The City",
                    session_number=2,
                ),
            )
            self.assertEqual(2, updated.session_number)

            deleted_rolls = rolls.delete_for_episode(episode_id)
            self.assertEqual(
                0,
                deleted_rolls.campaign_stats.num_rolls,
            )
            self.assertEqual(
                [],
                deleted_rolls.session_stats.rolls,
            )
            self.assertEqual([], db.exec(select(RollEntry)).all())
            self.assertIsNotNone(db.get(Episode, episode_id))

            deleted_episode = episodes.delete(episode_id)
            self.assertEqual(
                episode_id,
                deleted_episode.deleted_id,
            )
            self.assertIsNone(db.get(Episode, episode_id))

    def test_roll_mutations_reject_an_episode_from_another_campaign(self):
        with Session(self.engine) as db:
            first_campaign = self._create_campaign(db, "First")
            second_campaign = self._create_campaign(db, "Second")
            first_context = campaign_context(db, first_campaign)
            episode = EpisodeService(first_context).create(
                EpisodeData(
                    date="2026-07-23",
                    title="Arrival",
                    session_number=1,
                ),
            )

            with self.assertRaises(HTTPException) as context:
                RollService(
                    campaign_context(db, second_campaign)
                ).create(
                    RollCreate(session_id=episode.id, roll=10),
                )

            self.assertEqual(404, context.exception.status_code)
            self.assertEqual([], db.exec(select(RollEntry)).all())


if __name__ == "__main__":
    unittest.main()
