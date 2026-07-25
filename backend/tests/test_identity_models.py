from datetime import datetime, timedelta, timezone
import unittest

from sqlalchemy import event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth.enums import AccountTokenPurpose, SystemRole, UserStatus
from app.auth.models import (
    AccountToken,
    AuthSession,
    PasswordCredential,
    User,
)
from app.migrations import run_database_migrations


NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


class IdentityModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = sqlite_engine()
        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_normalized_username_is_unique(self):
        with Session(self.engine) as db:
            db.add(
                User(
                    username="Keeper",
                    normalized_username="keeper",
                    status=UserStatus.ACTIVE,
                )
            )
            db.commit()
            db.add(
                User(
                    username="keeper",
                    normalized_username="keeper",
                    status=UserStatus.ACTIVE,
                )
            )

            with self.assertRaises(IntegrityError):
                db.commit()

    def test_user_owns_one_credential_and_revocable_session(self):
        with Session(self.engine) as db:
            user = User(
                username="keeper",
                normalized_username="keeper",
                status=UserStatus.ACTIVE,
                system_role=SystemRole.ADMIN,
            )
            db.add(user)
            db.flush()
            db.add(
                PasswordCredential(
                    user_id=user.id,
                    password_hash="$argon2id$test",
                )
            )
            db.add(
                AuthSession(
                    user_id=user.id,
                    token_digest="a" * 64,
                    csrf_token_digest="b" * 64,
                    created_at=NOW,
                    last_used_at=NOW,
                    expires_at=NOW + timedelta(hours=12),
                    absolute_expires_at=NOW + timedelta(days=7),
                )
            )
            db.commit()

            self.assertIsNotNone(db.get(PasswordCredential, user.id))

    def test_account_token_records_purpose_and_issuer(self):
        with Session(self.engine) as db:
            admin = User(
                username="admin",
                normalized_username="admin",
                status=UserStatus.ACTIVE,
                system_role=SystemRole.ADMIN,
            )
            invited = User(
                username="invited",
                normalized_username="invited",
            )
            db.add_all([admin, invited])
            db.flush()
            token = AccountToken(
                user_id=invited.id,
                purpose=AccountTokenPurpose.ACTIVATION,
                token_digest="c" * 64,
                created_at=NOW,
                expires_at=NOW + timedelta(days=1),
                created_by_user_id=admin.id,
            )
            db.add(token)
            db.commit()
            db.refresh(token)

            self.assertEqual(
                AccountTokenPurpose.ACTIVATION,
                token.purpose,
            )
            self.assertEqual(admin.id, token.created_by_user_id)


class IdentityDevelopmentMigrationTests(unittest.TestCase):
    def test_existing_portable_baseline_gets_identity_tables(self):
        engine = sqlite_engine()
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE installation ("
                        "id INTEGER NOT NULL PRIMARY KEY, "
                        "installation_id VARCHAR NOT NULL, "
                        "mode VARCHAR NOT NULL, "
                        "initialized_at DATETIME NOT NULL, "
                        "CONSTRAINT ck_installation_singleton "
                        "CHECK (id = 1))"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TABLE alembic_version ("
                        "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO alembic_version (version_num) "
                        "VALUES ('0001_current_schema')"
                    )
                )

            run_database_migrations(engine)
            run_database_migrations(engine)

            tables = set(inspect(engine).get_table_names())
            self.assertTrue(
                {
                    "app_user",
                    "password_credential",
                    "auth_session",
                    "account_token",
                    "login_throttle",
                    "security_event",
                    "campaign_invitation",
                }.issubset(tables)
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
