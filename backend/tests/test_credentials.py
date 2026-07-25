from datetime import datetime, timedelta, timezone
import unittest

from argon2 import PasswordHasher
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.database import (
    AuthSession,
    PasswordCredential,
    User,
)
from app.models.enums import SystemRole, UserStatus
from app.services.credentials import (
    CredentialService,
    PasswordPolicyError,
    UsernamePolicyError,
    normalize_username,
    validate_password,
)
from app.services.identity_admin import (
    IdentityAdminError,
    IdentityAdminService,
)


NOW = datetime(2026, 7, 25, 15, 0, tzinfo=timezone.utc)
PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "a newer correct horse battery staple"


def test_hasher(*, memory_cost: int = 8192) -> PasswordHasher:
    return PasswordHasher(
        time_cost=1,
        memory_cost=memory_cost,
        parallelism=1,
    )


class CredentialPolicyTests(unittest.TestCase):
    def test_username_is_nfkc_normalized_and_casefolded(self):
        self.assertEqual("keeper", normalize_username("  Ｋeeper "))

    def test_username_rejects_spaces_and_leading_punctuation(self):
        for username in ("bad name", "_keeper"):
            with self.subTest(username=username):
                with self.assertRaises(UsernamePolicyError):
                    normalize_username(username)

    def test_password_requires_fifteen_characters_without_composition(self):
        with self.assertRaises(PasswordPolicyError):
            validate_password("too short")

        validate_password("a long passphrase")
        validate_password("十五文字以上の安全なパスフレーズ")


class IdentityDatabaseTestCase(unittest.TestCase):
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

    def add_user(self, db: Session, username: str = "keeper") -> User:
        user = User(
            username=username,
            normalized_username=normalize_username(username),
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.flush()
        return user


class CredentialServiceTests(IdentityDatabaseTestCase):
    def test_password_is_stored_only_as_argon2id_hash(self):
        with Session(self.engine) as db:
            user = self.add_user(db)
            service = CredentialService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: NOW,
            )

            credential = service.set_password(user, PASSWORD)
            db.commit()

            self.assertTrue(
                credential.password_hash.startswith("$argon2id$")
            )
            self.assertNotIn(PASSWORD, credential.password_hash)
            self.assertTrue(
                service.verify_password(credential, PASSWORD)
            )
            self.assertFalse(
                service.verify_password(credential, "wrong password")
            )

    def test_successful_verification_upgrades_old_hash_parameters(self):
        with Session(self.engine) as db:
            user = self.add_user(db)
            old_hash = test_hasher(memory_cost=4096).hash(PASSWORD)
            credential = PasswordCredential(
                user_id=user.id,
                password_hash=old_hash,
                password_changed_at=NOW,
            )
            db.add(credential)
            db.commit()
            service = CredentialService(
                db,
                password_hasher=test_hasher(memory_cost=8192),
                clock=lambda: NOW + timedelta(hours=1),
            )

            self.assertTrue(
                service.verify_password(credential, PASSWORD)
            )
            self.assertNotEqual(old_hash, credential.password_hash)

    def test_password_change_revokes_existing_sessions(self):
        with Session(self.engine) as db:
            user = self.add_user(db)
            service = CredentialService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: NOW,
            )
            service.set_password(
                user,
                PASSWORD,
                revoke_sessions=False,
            )
            session = AuthSession(
                user_id=user.id,
                token_digest="a" * 64,
                csrf_token_digest="b" * 64,
                created_at=NOW,
                last_used_at=NOW,
                expires_at=NOW + timedelta(hours=12),
                absolute_expires_at=NOW + timedelta(days=7),
            )
            db.add(session)
            db.commit()

            service.set_password(user, NEW_PASSWORD)
            db.commit()
            db.refresh(session)

            self.assertIsNotNone(session.revoked_at)


class IdentityAdminServiceTests(IdentityDatabaseTestCase):
    def test_first_admin_also_creates_non_login_custodian(self):
        with Session(self.engine) as db:
            service = IdentityAdminService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: NOW,
            )

            admin = service.create_initial_admin("Keeper", PASSWORD)
            users = db.exec(select(User).order_by(User.id)).all()

            self.assertEqual(SystemRole.ADMIN, admin.system_role)
            self.assertEqual(UserStatus.ACTIVE, admin.status)
            self.assertTrue(admin.can_login)
            custodian = next(
                user
                for user in users
                if user.system_role is SystemRole.CUSTODIAN
            )
            self.assertFalse(custodian.can_login)
            self.assertIsNone(
                db.get(PasswordCredential, custodian.id)
            )

    def test_second_bootstrap_admin_is_rejected(self):
        with Session(self.engine) as db:
            service = IdentityAdminService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: NOW,
            )
            service.create_initial_admin("keeper", PASSWORD)

            with self.assertRaises(IdentityAdminError):
                service.create_initial_admin("second-admin", PASSWORD)

    def test_offline_reset_replaces_hash_and_revokes_sessions(self):
        with Session(self.engine) as db:
            service = IdentityAdminService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: NOW,
            )
            admin = service.create_initial_admin("keeper", PASSWORD)
            session = AuthSession(
                user_id=admin.id,
                token_digest="c" * 64,
                csrf_token_digest="d" * 64,
                created_at=NOW,
                last_used_at=NOW,
                expires_at=NOW + timedelta(hours=12),
                absolute_expires_at=NOW + timedelta(days=7),
            )
            db.add(session)
            db.commit()

            service.reset_password("KEEPER", NEW_PASSWORD)
            credential = db.get(PasswordCredential, admin.id)
            db.refresh(session)

            self.assertTrue(
                service.credentials.verify_password(
                    credential,
                    NEW_PASSWORD,
                )
            )
            self.assertFalse(
                service.credentials.verify_password(
                    credential,
                    PASSWORD,
                )
            )
            self.assertIsNotNone(session.revoked_at)


if __name__ == "__main__":
    unittest.main()
