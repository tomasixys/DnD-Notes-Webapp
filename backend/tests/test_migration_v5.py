import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sqlalchemy import create_engine as create_sqlalchemy_engine, inspect, text
from sqlalchemy.pool import NullPool

from app.migrations import CURRENT_DATABASE_VERSION, run_database_migrations


class MigrationV5Tests(unittest.TestCase):
    def test_v5_migration_drops_player_character_column(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"

            # Create a mock schema version 4 database with player_character column
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    "CREATE TABLE campaign ("
                    "id INTEGER NOT NULL PRIMARY KEY, "
                    "name VARCHAR NOT NULL, "
                    "player_character VARCHAR NOT NULL DEFAULT '', "
                    "description VARCHAR NOT NULL DEFAULT ''"
                    ")"
                )
                conn.execute("PRAGMA user_version = 4")
                conn.commit()

            engine = create_sqlalchemy_engine(
                f"sqlite:///{db_path}",
                poolclass=NullPool,
            )

            try:
                run_database_migrations(engine)

                # Verify version updated to 5
                with closing(sqlite3.connect(db_path)) as conn:
                    version = conn.execute("PRAGMA user_version").fetchone()[0]
                    self.assertEqual(CURRENT_DATABASE_VERSION, version)

                # Verify player_character column was dropped
                with engine.connect() as conn:
                    columns = [
                        col["name"]
                        for col in inspect(conn).get_columns("campaign")
                    ]
                    self.assertNotIn("player_character", columns)
                    self.assertIn("name", columns)
                    self.assertIn("description", columns)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
