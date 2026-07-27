import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException
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
            )
            self.assertIsInstance(created, CampaignRead)
            campaign_id = created.id

            updated = campaigns.update(
                campaign_id,
                name="Updated",
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

            deleted = campaigns.delete(campaign_id)
            self.assertEqual(campaign_id, deleted.deleted_id)
            self.assertIsNone(db.get(Campaign, campaign_id))

    def test_backup_service_exports_and_imports_campaign_archive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "campaign.backup"
            with Session(self.engine) as db:
                created = CampaignService(db).create(
                    name="Test",
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
                self.assertNotEqual(campaign_id, imported.id)
                self.assertEqual(
                    2,
                    len(CampaignService(db).list_reads()),
                )

    def test_backup_import_rejects_invalid_data_without_creating_campaign(
        self,
    ):
        archive_data = io.BytesIO()
        with ZipFile(
            archive_data,
            "w",
            compression=ZIP_DEFLATED,
        ) as archive:
            archive.writestr(
                "backup.json",
                json.dumps(
                    {
                        "schema_version": 3,
                        "campaign": {},
                    }
                ),
            )

        with Session(self.engine) as db:
            with self.assertRaises(HTTPException) as error:
                CampaignBackupService(db).import_archive(
                    archive_data.getvalue()
                )

            self.assertEqual(400, error.exception.status_code)
            self.assertEqual(
                "Invalid backup data",
                error.exception.detail,
            )
            self.assertEqual([], db.exec(select(Campaign)).all())

    def test_active_character_ref_populated_in_campaign_reads(self):
        from app.models.api import CharacterCreate, PersonData
        from app.services.campaign_context import CampaignContext
        from app.services.characters import CharacterService

        with Session(self.engine) as db:
            campaign_read = CampaignService(db).create(name="Active Test")
            self.assertIsNone(campaign_read.active_character)

            context = CampaignContext.resolve(db, campaign_read.id)
            character_read = CharacterService(context).create(
                CharacterCreate(person=PersonData(name="Elrond"))
            )

            context.campaign.active_character_person_id = character_read.person.id
            db.add(context.campaign)
            db.commit()

            read_single = CampaignService(db).get_read(campaign_read.id)
            self.assertIsNotNone(read_single.active_character)
            self.assertEqual(character_read.person.id, read_single.active_character.id)
            self.assertEqual("Elrond", read_single.active_character.name)

            reads_list = CampaignService(db).list_reads()
            self.assertEqual(1, len(reads_list))
            self.assertIsNotNone(reads_list[0].active_character)
            self.assertEqual("Elrond", reads_list[0].active_character.name)

    def test_create_campaign_with_initial_character_and_faction(self):
        with Session(self.engine) as db:
            campaign = CampaignService(db).create(
                name="Deep World",
                character_name="Gloin",
                faction_name="Iron Daggers",
            )
            self.assertIsNotNone(campaign.active_character)
            self.assertEqual("Gloin", campaign.active_character.name)

    def test_update_campaign_creates_character_profile_if_missing(self):
        from app.models.api import PersonData
        from app.services.campaign_context import CampaignContext
        from app.services.people import PersonService

        with Session(self.engine) as db:
            campaign = CampaignService(db).create(name="Update Test")
            context = CampaignContext.resolve(db, campaign.id)
            person = PersonService(context).create(PersonData(name="Standalone Person"))

            # Update campaign setting active_character_person_id to a person without character profile
            updated = CampaignService(db).update(
                campaign.id,
                name="Update Test",
                active_character_person_id=person.id,
            )

            self.assertIsNotNone(updated.active_character)
            self.assertEqual(person.id, updated.active_character.id)
            self.assertEqual("Standalone Person", updated.active_character.name)


if __name__ == "__main__":
    unittest.main()
