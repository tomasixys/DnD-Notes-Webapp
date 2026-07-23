import unittest

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.dependencies.campaigns import verify_campaign
from app.models.database import Campaign


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

    def test_verify_campaign_preserves_not_found_response(self):
        with Session(self.engine) as db:
            with self.assertRaises(HTTPException) as context:
                verify_campaign(718123, db)

        self.assertEqual(404, context.exception.status_code)
        self.assertEqual("Campaign not found", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
