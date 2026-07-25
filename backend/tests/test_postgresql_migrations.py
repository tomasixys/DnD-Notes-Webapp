import os
import threading
import unittest
from uuid import uuid4

from argon2 import PasswordHasher
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import Session, create_engine

from app.auth.accounts import (
    AccountLifecycleError,
    AccountLifecycleService,
)
from app.auth.enums import SystemRole, UserStatus
from app.auth.models import LoginThrottle, User
from app.auth.throttling import LoginThrottleService
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
        self.assertIn("app_user", table_names)
        self.assertIn("login_throttle", table_names)
        self.assertIn("security_event", table_names)
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

    def test_activation_token_has_one_winner_under_concurrency(self):
        username_suffix = uuid4().hex
        with Session(self.engine) as db:
            admin = User(
                username=f"admin-{username_suffix}",
                normalized_username=f"admin-{username_suffix}",
                status=UserStatus.ACTIVE,
                system_role=SystemRole.ADMIN,
                can_login=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            invitation = AccountLifecycleService(
                db,
                password_hasher=PasswordHasher(
                    time_cost=1,
                    memory_cost=8192,
                    parallelism=1,
                ),
                token_factory=lambda size: f"token-{username_suffix}",
            ).invite_user(
                admin,
                f"player-{username_suffix}",
                lifetime_minutes=60,
            )

        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        def activate() -> None:
            with Session(self.engine) as db:
                service = AccountLifecycleService(
                    db,
                    password_hasher=PasswordHasher(
                        time_cost=1,
                        memory_cost=8192,
                        parallelism=1,
                    ),
                )
                barrier.wait()
                try:
                    service.activate(
                        invitation.token,
                        "correct horse battery staple",
                    )
                    outcome = "activated"
                except AccountLifecycleError:
                    db.rollback()
                    outcome = "rejected"
                with outcomes_lock:
                    outcomes.append(outcome)

        threads = [
            threading.Thread(target=activate),
            threading.Thread(target=activate),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(["activated", "rejected"], sorted(outcomes))

    def test_concurrent_source_failures_are_not_lost(self):
        digest = uuid4().hex
        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        def record_failure() -> None:
            with Session(self.engine) as db:
                service = LoginThrottleService(
                    db,
                    failure_limit=20,
                    window_seconds=300,
                    lock_seconds=300,
                )
                barrier.wait()
                service.record_failure(digest)
                db.commit()
                with outcomes_lock:
                    outcomes.append("recorded")

        threads = [
            threading.Thread(target=record_failure),
            threading.Thread(target=record_failure),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(["recorded", "recorded"], outcomes)
        with Session(self.engine) as db:
            throttle = db.get(LoginThrottle, digest)
            self.assertEqual(2, throttle.failed_attempts)
