import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from sqlmodel import Session

from app import database as database_module
from app.app_paths import configure_app_data_dir
from app.config import ApplicationSettings
from app.database import create_db_and_tables
from app.instance_lock import InstanceLock, InstanceLockError
from app.models.database import Campaign
from app.services.installations import InstallationService
from maintenance import export_campaign, inspect_installation


class InstanceLockTests(unittest.TestCase):
    def test_second_process_path_cannot_be_locked_concurrently(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "instance.lock"
            with InstanceLock(lock_path):
                with self.assertRaises(InstanceLockError):
                    with InstanceLock(lock_path):
                        pass


class MaintenanceCommandTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data_path = Path(self.directory.name) / "data"
        database_path = Path(self.directory.name) / "notes.db"
        self.settings = ApplicationSettings.model_validate(
            {
                "database": {
                    "url": f"sqlite:///{database_path.as_posix()}"
                },
                "storage": {
                    "backend": "filesystem",
                    "path": str(self.data_path),
                },
            }
        )
        configure_app_data_dir(self.data_path)
        engine = create_db_and_tables(self.settings)
        with Session(engine) as db:
            InstallationService(db).ensure(self.settings)
            db.add(Campaign(name="Recovery Test"))
            db.commit()
        engine.dispose()
        database_module._engine = None

    def tearDown(self):
        configure_app_data_dir(None)
        database_module._engine = None
        self.directory.cleanup()

    def test_inspection_returns_only_recovery_summary(self):
        summary = inspect_installation(self.settings)

        self.assertEqual("local", summary["mode"])
        self.assertEqual(1, summary["campaign_count"])
        self.assertEqual(
            [{"id": 1, "name": "Recovery Test"}],
            summary["campaigns"],
        )
        self.assertNotIn("password", summary)

    def test_campaign_can_be_exported_offline(self):
        output = Path(self.directory.name) / "recovery.backup"

        exported_path = export_campaign(
            self.settings,
            campaign_id=1,
            output=output,
        )

        self.assertEqual(output.resolve(), exported_path)
        self.assertTrue(output.is_file())
        with ZipFile(output) as archive:
            self.assertIn("backup.json", archive.namelist())


if __name__ == "__main__":
    unittest.main()
