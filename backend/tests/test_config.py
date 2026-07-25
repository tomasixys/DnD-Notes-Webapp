import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.build_profile import get_embedded_deployment_mode
from app.config import (
    CONFIG_PATH_ENV,
    ApplicationSettings,
    ConfigurationError,
    DeploymentMode,
    apply_server_overrides,
    load_application_settings,
)


HOSTED_CONFIG = """
[installation]
mode = "hosted"

[database]
url_env = "DND_NOTES_DATABASE_URL"

[storage]
backend = "object"
endpoint = "https://objects.example.test"
bucket = "dnd-notes"
access_key_env = "DND_NOTES_STORAGE_ACCESS_KEY"
secret_key_env = "DND_NOTES_STORAGE_SECRET_KEY"

[security]
session_secret_env = "DND_NOTES_SESSION_SECRET"

[server]
host = "127.0.0.1"
port = 8080
public_origin = "https://notes.example.test/"
open_browser = false
trusted_hosts = ["notes.example.test"]
"""

HOSTED_FILESYSTEM_CONFIG = HOSTED_CONFIG.replace(
    """[storage]
backend = "object"
endpoint = "https://objects.example.test"
bucket = "dnd-notes"
access_key_env = "DND_NOTES_STORAGE_ACCESS_KEY"
secret_key_env = "DND_NOTES_STORAGE_SECRET_KEY"
""",
    """[storage]
backend = "filesystem"
path = "D:/DnDNotesData"
""",
)


class ApplicationSettingsTests(unittest.TestCase):
    def test_source_tree_embeds_local_profile(self):
        self.assertEqual(
            DeploymentMode.LOCAL,
            get_embedded_deployment_mode(),
        )

    def test_defaults_are_safe_local_settings(self):
        settings = ApplicationSettings()

        self.assertEqual(
            DeploymentMode.LOCAL,
            settings.installation.mode,
        )
        self.assertEqual("127.0.0.1", settings.server.host)
        self.assertEqual(8000, settings.server.port)
        self.assertTrue(settings.server.open_browser)
        self.assertIsNone(settings.database.url)

    def test_local_mode_rejects_non_loopback_host(self):
        with self.assertRaises(ValueError):
            ApplicationSettings.model_validate(
                {
                    "installation": {"mode": "local"},
                    "server": {"host": "0.0.0.0"},
                }
            )

    def test_hosted_mode_requires_https_and_runtime_settings(self):
        with self.assertRaises(ValueError):
            ApplicationSettings.model_validate(
                {
                    "installation": {"mode": "hosted"},
                    "server": {
                        "host": "127.0.0.1",
                        "public_origin": "http://notes.example.test",
                        "open_browser": False,
                    },
                }
            )

    def test_server_override_is_revalidated(self):
        settings = ApplicationSettings()

        with self.assertRaises(ConfigurationError):
            apply_server_overrides(settings, host="0.0.0.0")

        updated = apply_server_overrides(settings, port=9123)
        self.assertEqual(9123, updated.server.port)

    def test_database_accepts_only_one_url_source(self):
        with self.assertRaises(ValueError):
            ApplicationSettings.model_validate(
                {
                    "database": {
                        "url": "sqlite:///notes.db",
                        "url_env": "DND_NOTES_DATABASE_URL",
                    }
                }
            )

    def test_security_rejects_inverted_session_and_lock_limits(self):
        with self.assertRaises(ValueError):
            ApplicationSettings.model_validate(
                {
                    "security": {
                        "session_lifetime_minutes": 60,
                        "session_absolute_lifetime_minutes": 30,
                    }
                }
            )
        with self.assertRaises(ValueError):
            ApplicationSettings.model_validate(
                {
                    "security": {
                        "login_initial_lock_seconds": 60,
                        "login_maximum_lock_seconds": 30,
                    }
                }
            )


class ApplicationSettingsFileTests(unittest.TestCase):
    def write_config(self, directory: str, content: str) -> Path:
        path = Path(directory) / "dnd-notes.toml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_and_normalizes_hosted_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, HOSTED_CONFIG)

            settings = load_application_settings(path)

        self.assertEqual(
            DeploymentMode.HOSTED,
            settings.installation.mode,
        )
        self.assertEqual(
            "https://notes.example.test",
            settings.server.public_origin,
        )
        self.assertEqual("dnd-notes", settings.storage.bucket)

    def test_environment_can_select_config_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(
                directory,
                "[server]\nport = 8765\n",
            )
            with patch.dict(
                os.environ,
                {CONFIG_PATH_ENV: str(path)},
                clear=False,
            ):
                settings = load_application_settings()

        self.assertEqual(8765, settings.server.port)

    def test_missing_config_path_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.toml"

            with self.assertRaises(ConfigurationError):
                load_application_settings(path)

    def test_unknown_fields_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(
                directory,
                "[server]\nport = 8000\nunknown = true\n",
            )

            with self.assertRaises(ConfigurationError) as error:
                load_application_settings(path)

        self.assertIn("unknown", str(error.exception))

    def test_hosted_application_mounts_authentication_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, HOSTED_CONFIG)
            settings = load_application_settings(path)

        from app.application import create_app

        application = create_app(
            settings,
            build_profile=DeploymentMode.HOSTED,
        )
        paths = set(application.openapi()["paths"])
        self.assertIn("/api/auth/login", paths)
        self.assertIn("/api/auth/session", paths)

    def test_local_application_mounts_only_session_bootstrap_route(self):
        from app.application import create_app

        application = create_app(
            ApplicationSettings(),
            build_profile=DeploymentMode.LOCAL,
        )
        paths = set(application.openapi()["paths"])
        self.assertIn("/api/auth/session", paths)
        self.assertNotIn("/api/auth/login", paths)
        self.assertNotIn("/api/auth/activate", paths)

    def test_runtime_settings_reject_config_from_another_build_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, HOSTED_CONFIG)
            settings = load_application_settings(path)

        from app.config import validate_build_profile

        with self.assertRaises(ConfigurationError) as error:
            validate_build_profile(settings, DeploymentMode.LOCAL)

        self.assertIn("build profile", str(error.exception).lower())

    def test_hosted_runtime_requires_every_referenced_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, HOSTED_CONFIG)
            settings = load_application_settings(path)

        from app.config import validate_runtime_secrets

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError):
                validate_runtime_secrets(settings)

        with patch.dict(
            os.environ,
            {
                "DND_NOTES_DATABASE_URL": (
                    "postgresql+psycopg://notes:secret@db/notes"
                ),
                "DND_NOTES_SESSION_SECRET": "s" * 32,
                "DND_NOTES_STORAGE_ACCESS_KEY": "access-key",
                "DND_NOTES_STORAGE_SECRET_KEY": "storage-secret",
            },
            clear=True,
        ):
            validate_runtime_secrets(settings)

    def test_hosted_mode_accepts_explicit_filesystem_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(
                directory,
                HOSTED_FILESYSTEM_CONFIG,
            )
            settings = load_application_settings(path)

        from app.config import StorageBackend, validate_runtime_secrets

        self.assertEqual(
            StorageBackend.FILESYSTEM,
            settings.storage.backend,
        )
        self.assertEqual(
            Path("D:/DnDNotesData"),
            settings.storage.path,
        )

        with patch.dict(
            os.environ,
            {
                "DND_NOTES_DATABASE_URL": (
                    "postgresql+psycopg://notes:secret@db/notes"
                ),
                "DND_NOTES_SESSION_SECRET": "s" * 32,
            },
            clear=True,
        ):
            validate_runtime_secrets(settings)

    def test_hosted_filesystem_storage_requires_an_absolute_path(self):
        invalid_config = HOSTED_FILESYSTEM_CONFIG.replace(
            'path = "D:/DnDNotesData"',
            'path = "relative/data"',
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(directory, invalid_config)

            with self.assertRaises(ConfigurationError):
                load_application_settings(path)


if __name__ == "__main__":
    unittest.main()
