import unittest

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.dependencies.campaigns import (
    get_campaign_context,
    verify_campaign,
)
from app.models.database import Campaign
from app.services.campaign_context import CampaignContext


class CampaignDependenciesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_verify_campaign_returns_existing_campaign(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test campaign")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            resolved_campaign = verify_campaign(campaign.id, db)

            self.assertEqual(campaign.id, resolved_campaign.id)

    def test_campaign_context_keeps_the_verified_campaign_and_session(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test campaign")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            context = get_campaign_context(campaign.id, db)

            self.assertIs(db, context.db)
            self.assertIs(campaign, context.campaign)
            self.assertEqual(campaign.id, context.campaign_id)

    def test_campaign_context_rejects_an_unflushed_campaign(self):
        with Session(self.engine) as db:
            with self.assertRaises(ValueError):
                CampaignContext(db, Campaign(name="Not flushed"))

    def test_verify_campaign_preserves_not_found_response(self):
        with Session(self.engine) as db:
            with self.assertRaises(HTTPException) as context:
                verify_campaign(718123, db)

        self.assertEqual(404, context.exception.status_code)
        self.assertEqual("Campaign not found", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
