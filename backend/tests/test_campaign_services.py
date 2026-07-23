import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.api import CampaignBackupExportRead, CampaignRead
from app.models.database import Campaign, Inventory
from app.services.campaign_backups import CampaignBackupService
from app.services.campaigns import CampaignService


class CampaignServiceTests(unittest.TestCase):
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

    def test_staged_creation_joins_the_outer_transaction(self):
        with Session(self.engine) as db:
            campaign = CampaignService(db).stage_create(name="Test")
            campaign_id = campaign.id
            inventory = db.exec(
                select(Inventory).where(
                    Inventory.campaign_id == campaign_id
                )
            ).one()
            inventory_id = inventory.id

            db.rollback()

            self.assertIsNone(db.get(Campaign, campaign_id))
            self.assertIsNone(db.get(Inventory, inventory_id))

    def test_standalone_crud_returns_current_state_and_commits_delete(self):
        with Session(self.engine) as db:
            campaigns = CampaignService(db)
            created = campaigns.create(
                name="Test",
                player_character="Nalia",
            )
            self.assertIsInstance(created, CampaignRead)
            campaign_id = created.id

            updated = campaigns.update(
                campaign_id,
                name="Updated",
                player_character="Nalia",
                description="A changed campaign",
            )

            self.assertIsInstance(updated, CampaignRead)
            self.assertEqual("Updated", updated.name)
            self.assertEqual(
                "A changed campaign",
                updated.description,
            )
            self.assertEqual(0, updated.session_count)
            self.assertEqual(1, len(campaigns.list_reads()))

            self.assertEqual(
                {"deleted": True},
                campaigns.delete(campaign_id),
            )
            self.assertIsNone(db.get(Campaign, campaign_id))

    def test_backup_service_exports_and_imports_campaign_archive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "campaign.backup"
            with Session(self.engine) as db:
                created = CampaignService(db).create(
                    name="Test",
                    player_character="Nalia",
                    description="An expedition",
                )
                campaign_id = created.id
                backups = CampaignBackupService(db)

                with patch(
                    "app.services.campaign_backups."
                    "make_backup_archive_path",
                    return_value=(archive_path, "campaign.backup"),
                ):
                    exported = backups.export(campaign_id)

                imported = backups.import_archive(
                    archive_path.read_bytes()
                )

                self.assertIsInstance(
                    exported,
                    CampaignBackupExportRead,
                )
                self.assertIsInstance(imported, CampaignRead)
                self.assertEqual("campaign.backup", exported.filename)
                self.assertEqual("Test", imported.name)
                self.assertEqual("Nalia", imported.player_character)
                self.assertNotEqual(campaign_id, imported.id)
                self.assertEqual(
                    2,
                    len(CampaignService(db).list_reads()),
                )


if __name__ == "__main__":
    unittest.main()
