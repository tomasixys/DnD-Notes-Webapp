import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.app_paths import configure_app_data_dir
from app.authorization.context import CampaignContext
from app.backup_downloads import backup_file_response
from app.file_storage import (
    cleanup_expired_backup_archives,
    resolve_stored_image,
    save_image_from_uploadfile,
    validate_client_filename,
    write_image_from_bytes,
)
from app.models.api import CharacterCreate, PersonData
from app.models.database import Campaign
from app.routers.assets import (
    CampaignAssetKind,
    get_campaign_asset,
    get_character_portrait,
)
from app.services.campaign_backups import (
    CampaignBackupArchive,
    CampaignBackupService,
)
from app.services.campaigns import CampaignService
from app.services.characters import CharacterService
from tests.authorization_helpers import campaign_context, create_user


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 4), color=(31, 71, 122)).save(
        output,
        format="PNG",
    )
    return output.getvalue()


def minimal_backup_json(**campaign_overrides) -> str:
    campaign = {
        "name": "Imported",
        "player_character": "",
        "description": "",
        "image_archive_path": "",
        "banner_archive_path": "",
        "active_character_person_backup_id": None,
    }
    campaign.update(campaign_overrides)
    return json.dumps(
        {
            "schema_version": 3,
            "campaign": campaign,
            "sessions": [],
            "people": [],
            "characters": [],
            "locations": [],
            "factions": [],
            "inventories": [],
        }
    )


class ProtectedFileTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        configure_app_data_dir(Path(self.temporary_directory.name))

    def tearDown(self):
        configure_app_data_dir(None)
        self.temporary_directory.cleanup()


class ImageStorageTests(ProtectedFileTestCase):
    def upload(self, data: bytes, content_type: str = "image/png"):
        return SimpleNamespace(
            filename="portrait.png",
            content_type=content_type,
            file=io.BytesIO(data),
        )

    def test_image_bytes_control_type_and_extension(self):
        relative_path = save_image_from_uploadfile(
            7,
            self.upload(png_bytes()),
        )
        stored = resolve_stored_image(relative_path)

        self.assertEqual("image/png", stored.media_type)
        self.assertEqual(".png", stored.path.suffix)
        self.assertTrue(stored.path.is_file())

        with self.assertRaises(HTTPException) as mismatch:
            save_image_from_uploadfile(
                7,
                self.upload(png_bytes(), "image/jpeg"),
            )
        self.assertEqual(400, mismatch.exception.status_code)

        with self.assertRaises(HTTPException) as invalid:
            save_image_from_uploadfile(
                7,
                self.upload(b"<script>not an image</script>"),
            )
        self.assertEqual(400, invalid.exception.status_code)

    def test_filename_extension_and_storage_traversal_are_rejected(self):
        with self.assertRaises(HTTPException):
            validate_client_filename("../portrait.png")
        with self.assertRaises(HTTPException):
            validate_client_filename(
                "campaign.zip",
                required_suffix=".backup",
            )
        with self.assertRaises(HTTPException) as mismatch:
            write_image_from_bytes(1, ".jpg", png_bytes())
        self.assertEqual(400, mismatch.exception.status_code)
        with self.assertRaises(HTTPException) as hidden:
            resolve_stored_image("../outside.png")
        self.assertEqual(404, hidden.exception.status_code)

    def test_image_byte_limit_is_enforced_before_storage(self):
        with patch("app.file_storage.MAX_IMAGE_SIZE_BYTES", 4):
            with self.assertRaises(HTTPException) as oversized:
                save_image_from_uploadfile(
                    1,
                    self.upload(png_bytes()),
                )
        self.assertEqual("Image is too large.", oversized.exception.detail)

    def test_expired_transient_backups_are_removed(self):
        from app.app_paths import get_transient_backups_dir

        backup = get_transient_backups_dir() / "stale.backup"
        backup.write_bytes(b"archive")
        os.utime(backup, (10, 10))

        removed = cleanup_expired_backup_archives(
            now=100,
            maximum_age_seconds=60,
        )

        self.assertEqual(1, removed)
        self.assertFalse(backup.exists())

    def test_download_response_deletes_archive_after_transfer(self):
        archive_path = Path(self.temporary_directory.name) / "test.backup"
        archive_path.write_bytes(b"backup")
        response = backup_file_response(
            CampaignBackupArchive(
                path=archive_path,
                filename="test.backup",
            )
        )

        self.assertEqual("private, no-store", response.headers["cache-control"])
        response.background.func(
            *response.background.args,
            **response.background.kwargs,
        )
        self.assertFalse(archive_path.exists())


class AssetAuthorizationTests(ProtectedFileTestCase):
    def setUp(self):
        super().setUp()
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
        super().tearDown()

    def test_campaign_asset_requires_current_membership(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Private")
            db.add(campaign)
            db.flush()
            context = campaign_context(db, campaign)
            campaign.image_path = write_image_from_bytes(
                campaign.id,
                ".png",
                png_bytes(),
            )
            db.add(campaign)
            db.commit()

            campaign_read = CampaignService(
                db,
                context.user,
            ).get_read(campaign.id)
            self.assertEqual(
                f"campaigns/{campaign.id}/assets/image",
                campaign_read.image_url,
            )
            self.assertNotIn("uploads", campaign_read.image_url)

            response = get_campaign_asset(
                CampaignAssetKind.IMAGE,
                context,
            )
            self.assertEqual("image/png", response.media_type)
            self.assertEqual(
                "private, no-store",
                response.headers["cache-control"],
            )

            db.delete(context.membership)
            db.commit()
            with self.assertRaises(HTTPException) as revoked:
                CampaignContext.resolve(
                    db,
                    campaign.id,
                    context.user,
                )
            self.assertEqual(404, revoked.exception.status_code)

    def test_character_asset_cannot_cross_campaign_boundary(self):
        with Session(self.engine) as db:
            first = Campaign(name="First")
            second = Campaign(name="Second")
            db.add(first)
            db.add(second)
            db.flush()
            first_context = campaign_context(db, first)
            second_context = campaign_context(db, second)
            character = CharacterService(second_context).create(
                CharacterCreate(person=PersonData(name="Hidden"))
            )

            with self.assertRaises(HTTPException) as hidden:
                get_character_portrait(
                    character.person.id,
                    first_context,
                )
            self.assertEqual(404, hidden.exception.status_code)


class BackupArchiveSafetyTests(ProtectedFileTestCase):
    def setUp(self):
        super().setUp()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()
        super().tearDown()

    def import_data(self, data: bytes):
        with Session(self.engine) as db:
            user = create_user(db)
            return CampaignBackupService(db, user).import_archive(data)

    def test_archive_traversal_and_expansion_are_rejected(self):
        traversal = io.BytesIO()
        with ZipFile(
            traversal,
            "w",
            compression=ZIP_DEFLATED,
        ) as archive:
            archive.writestr("backup.json", minimal_backup_json())
            archive.writestr("../outside.txt", "hidden")

        with self.assertRaises(HTTPException) as unsafe:
            self.import_data(traversal.getvalue())
        self.assertEqual("Invalid backup archive path", unsafe.exception.detail)

        expanded = io.BytesIO()
        with ZipFile(
            expanded,
            "w",
            compression=ZIP_DEFLATED,
        ) as archive:
            archive.writestr("backup.json", minimal_backup_json())
            archive.writestr("large.txt", "123456")

        with patch(
            "app.services.campaign_backups."
            "MAX_BACKUP_EXPANDED_BYTES",
            5,
        ):
            with self.assertRaises(HTTPException) as oversized:
                self.import_data(expanded.getvalue())
        self.assertEqual(
            "Expanded backup archive is too large",
            oversized.exception.detail,
        )

    def test_backup_upload_size_is_bounded(self):
        with patch(
            "app.services.campaign_backups.MAX_BACKUP_UPLOAD_BYTES",
            4,
        ):
            with self.assertRaises(HTTPException) as oversized:
                self.import_data(b"12345")
        self.assertEqual(
            "Backup archive is too large",
            oversized.exception.detail,
        )

    def test_imported_image_must_decode_and_rolls_back_campaign(self):
        archive_data = io.BytesIO()
        with ZipFile(
            archive_data,
            "w",
            compression=ZIP_DEFLATED,
        ) as archive:
            archive.writestr(
                "backup.json",
                minimal_backup_json(
                    image_archive_path="assets/campaign-image.png",
                ),
            )
            archive.writestr(
                "assets/campaign-image.png",
                b"not an image",
            )

        with self.assertRaises(HTTPException) as invalid:
            self.import_data(archive_data.getvalue())
        self.assertEqual(
            "Invalid or unsafe image data.",
            invalid.exception.detail,
        )
