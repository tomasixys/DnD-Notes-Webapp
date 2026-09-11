import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, inspect, text

from .development import migrate_development_schema
from .v1 import migrate_to_v1
from .v2 import migrate_to_v2
from .v3 import migrate_to_v3
from .v4 import migrate_to_v4
from .v5 import migrate_to_v5
from .v6 import migrate_to_v6
from .v7 import migrate_to_v7


CURRENT_DATABASE_VERSION = 7
PORTABLE_BASELINE_REVISION = "0001_current_schema"
PORTABLE_HEAD_REVISION = "0004_add_issue_reports"
PORTABLE_MIGRATION_DIR = Path(__file__).resolve().parent / "portable"

MIGRATIONS = {
    1: migrate_to_v1,
    2: migrate_to_v2,
    3: migrate_to_v3,
    4: migrate_to_v4,
    5: migrate_to_v5,
    6: migrate_to_v6,
    7: migrate_to_v7,
}


class MigrationStateError(RuntimeError):
    """Raised when a database cannot be adopted without an explicit process."""


def get_database_version(database_path: Path) -> int:
    if not database_path.exists():
        return 0

    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0


def backup_database_before_migration(database_path: Path) -> Path | None:
    if (
        not database_path.exists()
        or get_database_version(database_path) >= CURRENT_DATABASE_VERSION
    ):
        return None

    backup_path = database_path.with_name(
        f"{database_path.name}.pre-v{CURRENT_DATABASE_VERSION}.bak"
    )
    if not backup_path.exists():
        shutil.copy2(database_path, backup_path)
    return backup_path


def _run_legacy_sqlite_migrations(connection: Connection) -> None:
    version = int(
        connection.execute(text("PRAGMA user_version")).scalar_one()
    )

    if version > CURRENT_DATABASE_VERSION:
        raise RuntimeError(
            "Database was created by a newer version of Campaign Notes"
        )

    for target_version in range(
        version + 1,
        CURRENT_DATABASE_VERSION + 1,
    ):
        migration = MIGRATIONS[target_version]
        migration(connection)
        connection.execute(
            text(f"PRAGMA user_version = {target_version}")
        )

    migrate_development_schema(connection)


def _alembic_config(connection: Connection) -> Config:
    config = Config()
    config.set_main_option(
        "script_location",
        str(PORTABLE_MIGRATION_DIR),
    )
    config.attributes["connection"] = connection
    return config


def _application_tables(connection: Connection) -> set[str]:
    return {
        table_name
        for table_name in inspect(connection).get_table_names()
        if table_name != "alembic_version"
    }


def run_database_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        config = _alembic_config(connection)

        if "alembic_version" in tables:
            command.upgrade(config, "head")
            migrate_development_schema(connection)
            return

        application_tables = _application_tables(connection)
        if not application_tables:
            command.upgrade(config, "head")
            migrate_development_schema(connection)
            if connection.dialect.name == "sqlite":
                connection.execute(
                    text(f"PRAGMA user_version = {CURRENT_DATABASE_VERSION}")
                )
            return

        if connection.dialect.name != "sqlite":
            raise MigrationStateError(
                "Refusing to adopt a non-empty PostgreSQL database without "
                "Alembic version history. Use an empty database or an "
                "explicit, reviewed baseline process."
            )

        _run_legacy_sqlite_migrations(connection)
        command.stamp(config, "head")
        migrate_development_schema(connection)
