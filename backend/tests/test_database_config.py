import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

from app.config import ApplicationSettings, ConfigurationError
from app import database as database_module
from app.database import (
    create_database_engine,
    create_db_and_tables,
    resolve_database_url,
)
from app.migrations import (
    PORTABLE_HEAD_REVISION,
    run_database_migrations,
)


def hosted_settings() -> ApplicationSettings:
    return ApplicationSettings.model_validate(
        {
            "installation": {"mode": "hosted"},
            "database": {"url_env": "DND_NOTES_DATABASE_URL"},
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
                "public_origin": "https://notes.example.test",
                "open_browser": False,
                "trusted_hosts": ["notes.example.test"],
            },
        }
    )


class DatabaseConfigurationTests(unittest.TestCase):
    def test_default_database_uses_application_sqlite_path(self):
        with tempfile.TemporaryDirectory() as directory:
            expected_path = Path(directory) / "notes.db"
            with patch(
                "app.database.get_database_path",
                return_value=expected_path,
            ):
                url = resolve_database_url(ApplicationSettings())

        self.assertEqual("sqlite", url.get_backend_name())
        self.assertEqual(expected_path.as_posix(), url.database)

    def test_local_mode_rejects_non_sqlite_database(self):
        settings = ApplicationSettings.model_validate(
            {
                "database": {
                    "url": "postgresql+psycopg://localhost/notes",
                }
            }
        )

        with self.assertRaises(ConfigurationError):
            resolve_database_url(settings)

    def test_hosted_database_url_comes_from_environment(self):
        settings = hosted_settings()
        database_url = (
            "postgresql+psycopg://notes:secret@db.example.test/notes"
        )
        with patch.dict(
            os.environ,
            {"DND_NOTES_DATABASE_URL": database_url},
            clear=False,
        ):
            url = resolve_database_url(settings)

        self.assertEqual("postgresql", url.get_backend_name())
        self.assertEqual("db.example.test", url.host)

    def test_missing_hosted_database_environment_variable_fails(self):
        settings = hosted_settings()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError) as error:
                resolve_database_url(settings)

        self.assertIn(
            "DND_NOTES_DATABASE_URL",
            str(error.exception),
        )

    def test_hosted_database_requires_the_psycopg_driver(self):
        settings = hosted_settings()
        with patch.dict(
            os.environ,
            {
                "DND_NOTES_DATABASE_URL": (
                    "postgresql://notes:secret@db.example.test/notes"
                )
            },
            clear=False,
        ):
            with self.assertRaises(ConfigurationError) as error:
                resolve_database_url(settings)

        self.assertIn("postgresql+psycopg", str(error.exception))

    def test_sqlite_engine_enables_foreign_keys(self):
        settings = ApplicationSettings.model_validate(
            {"database": {"url": "sqlite://"}}
        )
        engine = create_database_engine(settings)
        try:
            with engine.connect() as connection:
                enabled = connection.execute(
                    text("PRAGMA foreign_keys")
                ).scalar_one()
            self.assertEqual(1, enabled)
        finally:
            engine.dispose()

    def test_configured_sqlite_database_is_initialized_and_registered(self):
        previous_engine = database_module._engine
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "configured.db"
            settings = ApplicationSettings.model_validate(
                {
                    "database": {
                        "url": f"sqlite:///{database_path.as_posix()}"
                    }
                }
            )
            engine = create_db_and_tables(settings)
            try:
                self.assertIs(engine, database_module.get_engine())
                with engine.connect() as connection:
                    table = connection.execute(
                        text(
                            "SELECT name FROM sqlite_master "
                            "WHERE type = 'table' AND name = 'installation'"
                        )
                    ).scalar_one()
                    revision = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one()
                self.assertEqual("installation", table)
                self.assertEqual(PORTABLE_HEAD_REVISION, revision)
            finally:
                engine.dispose()
                database_module._engine = previous_engine

    def test_portable_migration_runner_is_idempotent(self):
        settings = ApplicationSettings.model_validate(
            {"database": {"url": "sqlite://"}}
        )
        engine = create_database_engine(settings)
        try:
            run_database_migrations(engine)
            run_database_migrations(engine)
            with engine.connect() as connection:
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            self.assertEqual(PORTABLE_HEAD_REVISION, revision)
        finally:
            engine.dispose()

    def test_portable_migration_removes_legacy_session_number(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "portable.db"
            settings = ApplicationSettings.model_validate(
                {
                    "database": {
                        "url": f"sqlite:///{database_path.as_posix()}"
                    }
                }
            )
            engine = create_database_engine(settings)
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "CREATE TABLE campaign ("
                            "id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE TABLE sessionnote ("
                            "id INTEGER PRIMARY KEY, "
                            "campaign_id INTEGER NOT NULL, "
                            "title VARCHAR NOT NULL, "
                            "content VARCHAR NOT NULL, "
                            "date VARCHAR NOT NULL, "
                            "session_number INTEGER NOT NULL)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX ix_sessionnote_session_number "
                            "ON sessionnote (session_number)"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO sessionnote VALUES "
                            "(7, 1, 'Arrival', 'Notes', '2026-01-05', 12)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE TABLE app_user ("
                            "id INTEGER PRIMARY KEY)"
                        )
                    )
                    connection.execute(
                        text("INSERT INTO app_user VALUES (3)")
                    )
                    connection.execute(
                        text(
                            "CREATE TABLE campaign_membership ("
                            "id INTEGER PRIMARY KEY, "
                            "campaign_id INTEGER NOT NULL, "
                            "user_id INTEGER NOT NULL, "
                            "role VARCHAR NOT NULL, "
                            "is_custodial BOOLEAN NOT NULL)"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO campaign_membership VALUES "
                            "(4, 1, 3, 'owner', FALSE)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE TABLE rollentry ("
                            "id INTEGER PRIMARY KEY, "
                            "session_id INTEGER NOT NULL, "
                            "roll INTEGER NOT NULL)"
                        )
                    )
                    connection.execute(
                        text("INSERT INTO rollentry VALUES (8, 7, 18)")
                    )
                    connection.execute(
                        text(
                            "CREATE TABLE alembic_version ("
                            "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO alembic_version VALUES "
                            "('0001_current_schema')"
                        )
                    )

                run_database_migrations(engine)

                with engine.connect() as connection:
                    columns = {
                        row[1]
                        for row in connection.execute(
                            text("PRAGMA table_info(sessionnote)")
                        )
                    }
                    episode = connection.execute(
                        text(
                            "SELECT id, date, title, content "
                            "FROM sessionnote"
                        )
                    ).one()
                    roll = connection.execute(
                        text(
                            "SELECT id, session_id, user_id, roll "
                            "FROM rollentry"
                        )
                    ).one()
                    revision = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one()

                self.assertNotIn("session_number", columns)
                self.assertEqual(
                    (7, "2026-01-05", "Arrival", "Notes"),
                    episode,
                )
                self.assertEqual((8, 7, 3, 18), roll)
                self.assertEqual(PORTABLE_HEAD_REVISION, revision)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
