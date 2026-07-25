import os
import unittest
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import Session, create_engine

from app.migrations import (
    PORTABLE_BASELINE_REVISION,
    run_database_migrations,
)
from app.models.database import Installation


TEST_DATABASE_URL_ENV = "DND_NOTES_TEST_POSTGRES_URL"
ALLOW_MUTATION_ENV = "DND_NOTES_TEST_POSTGRES_ALLOW_MUTATION"


@unittest.skipUnless(
    os.environ.get(TEST_DATABASE_URL_ENV)
    and os.environ.get(ALLOW_MUTATION_ENV) == "1",
    "PostgreSQL integration database is not configured",
)
class PostgreSQLMigrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_url = make_url(os.environ[TEST_DATABASE_URL_ENV])
        if base_url.get_backend_name() != "postgresql":
            raise RuntimeError(
                f"{TEST_DATABASE_URL_ENV} must use PostgreSQL"
            )

        cls.schema_name = f"dnd_notes_test_{uuid4().hex}"
        cls.admin_engine = create_engine(base_url, pool_pre_ping=True)
        with cls.admin_engine.begin() as connection:
            connection.execute(CreateSchema(cls.schema_name))

        schema_url = base_url.update_query_dict(
            {"options": f"-csearch_path={cls.schema_name}"}
        )
        cls.engine = create_engine(schema_url, pool_pre_ping=True)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        with cls.admin_engine.begin() as connection:
            connection.execute(
                DropSchema(cls.schema_name, cascade=True)
            )
        cls.admin_engine.dispose()

    def test_baseline_creates_and_reuses_current_schema(self):
        run_database_migrations(self.engine)
        run_database_migrations(self.engine)

        table_names = set(inspect(self.engine).get_table_names())
        self.assertIn("campaign", table_names)
        self.assertIn("installation", table_names)
        self.assertIn("alembic_version", table_names)

        with self.engine.begin() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        self.assertEqual(PORTABLE_BASELINE_REVISION, revision)

        with Session(self.engine) as db:
            db.add(
                Installation(
                    installation_id=f"postgres-{uuid4()}",
                    mode="hosted",
                )
            )
            db.commit()
            self.assertIsNotNone(db.get(Installation, 1))
