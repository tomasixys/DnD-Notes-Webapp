from datetime import datetime, timezone
import unittest

from sqlalchemy import event, inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import ApplicationSettings
from app.migrations.development import migrate_development_schema
from app.models.database import Campaign, Installation
from app.services.installations import (
    InstallationService,
    InstallationStateError,
)


FIXED_TIME = datetime(2026, 7, 23, 20, 0, tzinfo=timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def local_settings() -> ApplicationSettings:
    return ApplicationSettings()


def hosted_settings() -> ApplicationSettings:
    return ApplicationSettings.model_validate(
        {
            "installation": {"mode": "hosted"},
            "database": {
                "url_env": "DND_NOTES_DATABASE_URL",
            },
            "storage": {
                "backend": "object",
                "endpoint": "https://objects.example.test",
                "bucket": "dnd-notes",
                "access_key_env": "DND_NOTES_STORAGE_ACCESS_KEY",
                "secret_key_env": "DND_NOTES_STORAGE_SECRET_KEY",
            },
            "security": {
                "session_secret_env": "DND_NOTES_SESSION_SECRET",
            },
            "server": {
                "host": "127.0.0.1",
                "public_origin": "https://notes.example.test",
                "open_browser": False,
                "trusted_hosts": ["notes.example.test"],
            },
        }
    )


class InstallationServiceTests(unittest.TestCase):
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

    def service(self, db: Session) -> InstallationService:
        return InstallationService(
            db,
            id_factory=lambda: "installation-test-id",
            clock=lambda: FIXED_TIME,
        )

    def test_initializes_local_installation(self):
        with Session(self.engine) as db:
            installation = self.service(db).ensure(local_settings())

            self.assertEqual(1, installation.id)
            self.assertEqual(
                "installation-test-id",
                installation.installation_id,
            )
            self.assertEqual("local", installation.mode)
            self.assertEqual(
                FIXED_TIME,
                as_utc(installation.initialized_at),
            )

    def test_reuses_existing_installation_without_mutating_it(self):
        with Session(self.engine) as db:
            first = self.service(db).ensure(hosted_settings())
            second = self.service(db).ensure(hosted_settings())

            self.assertEqual(first.installation_id, second.installation_id)

    def test_rejects_mode_change_after_initialization(self):
        with Session(self.engine) as db:
            self.service(db).ensure(local_settings())

            with self.assertRaises(InstallationStateError) as error:
                self.service(db).ensure(hosted_settings())

        self.assertIn("mode mismatch", str(error.exception).lower())

    def test_initializes_hosted_installation_without_credentials(self):
        with Session(self.engine) as db:
            installation = self.service(db).ensure(hosted_settings())

            self.assertEqual("hosted", installation.mode)
            self.assertEqual(
                FIXED_TIME,
                as_utc(installation.initialized_at),
            )

    def test_existing_campaign_database_can_only_be_claimed_locally(self):
        with Session(self.engine) as db:
            db.add(Campaign(name="Legacy campaign"))
            db.commit()

            with self.assertRaises(InstallationStateError):
                self.service(db).ensure(hosted_settings())

            self.assertIsNone(db.get(Installation, 1))

            installation = self.service(db).ensure(local_settings())
            self.assertEqual("local", installation.mode)


class InstallationMigrationTests(unittest.TestCase):
    def test_development_migration_creates_installation_table_idempotently(self):
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                migrate_development_schema(connection)
                migrate_development_schema(connection)

            inspector = inspect(engine)
            self.assertIn("installation", inspector.get_table_names())
            self.assertEqual(
                {
                    "id",
                    "installation_id",
                    "mode",
                    "initialized_at",
                },
                {
                    column["name"]
                    for column in inspector.get_columns("installation")
                },
            )
            self.assertIn(
                "ix_installation_installation_id",
                {
                    index["name"]
                    for index in inspector.get_indexes("installation")
                },
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
