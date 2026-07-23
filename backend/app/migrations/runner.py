import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy import Engine, text

from .development import migrate_development_schema
from .v1 import migrate_to_v1
from .v2 import migrate_to_v2
from .v3 import migrate_to_v3


CURRENT_DATABASE_VERSION = 3

MIGRATIONS = {
    1: migrate_to_v1,
    2: migrate_to_v2,
    3: migrate_to_v3,
}


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


def run_database_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
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

        # This hook is deliberately unversioned and must remain idempotent.
        # Before a release, its work is moved into the next numbered module.
        migrate_development_schema(connection)
