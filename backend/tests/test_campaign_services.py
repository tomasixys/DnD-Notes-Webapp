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

from app.models.api import CampaignRead
from app.models.database import Campaign, Episode, Inventory
from app.services.campaign_backups import (
    CampaignBackupArchive,
    CampaignBackupService,
)
from app.services.campaigns import CampaignService
from tests.authorization_helpers import create_user


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

    def test_campaign_character_name_belongs_to_the_requesting_membership(self):
        from app.authorization.enums import CampaignRole
        from app.models.database import Person, CharacterProfile
        from tests.authorization_helpers import campaign_context
        with Session(self.engine) as db:
            campaign = Campaign(name="Shared", player_character="Legacy owner's name")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            member = campaign_context(db, campaign, role=CampaignRole.MEMBER, user=create_user(db))
            viewer = campaign_context(db, campaign, role=CampaignRole.VIEWER, user=create_user(db))
            for context, name in ((owner, "Owner character"), (member, "Member character")):
                person = Person(campaign_id=campaign.id, name=name)
                db.add(person)
                db.flush()
                db.add(CharacterProfile(person_id=person.id))
                db.flush()
                context.membership.assigned_character_person_id = person.id
                context.membership.active_character_person_id = person.id
                db.add(context.membership)
            db.commit()
            for context, expected in ((owner, "Owner character"), (member, "Member character"), (viewer, "")):
                service = CampaignService(db, context.user)
                self.assertEqual(expected, service.get_read(campaign.id).player_character)
                self.assertEqual(expected, service.list_reads()[0].player_character)

    def test_local_campaign_keeps_legacy_character_summary_without_a_profile(self):
        with Session(self.engine) as db:
            local_user = create_user(db, can_login=False)
            service = CampaignService(db, local_user)
            campaign = service.create(name="Local", player_character="Legacy character")
            self.assertEqual("Legacy character", service.get_read(campaign.id).player_character)

    def tearDown(self):
        self.engine.dispose()

    def test_staged_creation_joins_the_outer_transaction(self):
        with Session(self.engine) as db:
            user = create_user(db)
            context = CampaignService(db, user).stage_create(name="Test")
            campaign_id = context.campaign_id
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
            user = create_user(db)
            campaigns = CampaignService(db, user)
            created = campaigns.create(
                name="Test",
                player_character="Nalia",
            )
            self.assertIsInstance(created, CampaignRead)
            campaign_id = created.id

            context = campaigns.get_context(campaign_id)
            updated = campaigns.update(
                context,
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

            deleted = campaigns.delete(context)
            self.assertEqual(campaign_id, deleted.deleted_id)
            self.assertIsNone(db.get(Campaign, campaign_id))

    def test_backup_service_exports_and_imports_campaign_archive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "campaign.backup"
            with Session(self.engine) as db:
                user = create_user(db)
                campaigns = CampaignService(db, user)
                created = campaigns.create(
                    name="Test",
                    player_character="Nalia",
                    description="An expedition",
                )
                campaign_id = created.id
                backups = CampaignBackupService(db, user)

                with patch(
                    "app.services.campaign_backups."
                    "make_backup_archive_path",
                    return_value=(archive_path, "campaign.backup"),
                ):
                    exported = backups.export(
                        campaigns.get_context(campaign_id)
                    )

                imported = backups.import_archive(
                    archive_path.read_bytes()
                )

                self.assertIsInstance(
                    exported,
                    CampaignBackupArchive,
                )
                self.assertIsInstance(imported, CampaignRead)
                self.assertEqual("campaign.backup", exported.filename)
                self.assertEqual("Test", imported.name)
                self.assertEqual("", imported.player_character)
                self.assertEqual("Nalia", db.get(Campaign, imported.id).player_character)
                self.assertNotEqual(campaign_id, imported.id)
                self.assertEqual(
                    2,
                    len(campaigns.list_reads()),
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
            user = create_user(db)
            with self.assertRaises(HTTPException) as error:
                CampaignBackupService(db, user).import_archive(
                    archive_data.getvalue()
                )

            self.assertEqual(400, error.exception.status_code)
            self.assertEqual(
                "Invalid backup data",
                error.exception.detail,
            )
            self.assertEqual([], db.exec(select(Campaign)).all())

    def test_version_four_backup_ignores_stored_session_numbers(self):
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
                        "schema_version": 4,
                        "campaign": {"name": "Legacy campaign"},
                        "sessions": [
                            {
                                "date": "2026-01-05",
                                "title": "Arrival",
                                "description": "Reached the city",
                                "session_number": 12,
                            }
                        ],
                    }
                ),
            )

        with Session(self.engine) as db:
            user = create_user(db)
            imported = CampaignBackupService(db, user).import_archive(
                archive_data.getvalue()
            )
            episode = db.exec(
                select(Episode).where(
                    Episode.campaign_id == imported.id
                )
            ).one()

            self.assertEqual("2026-01-05", episode.date)
            self.assertEqual("Arrival", episode.title)
            self.assertFalse(hasattr(episode, "session_number"))


if __name__ == "__main__":
    unittest.main()
