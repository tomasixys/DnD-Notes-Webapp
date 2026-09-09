from datetime import datetime, timedelta, timezone
import unittest

from argon2 import PasswordHasher
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth.accounts import (
    AccountLifecycleError,
    AccountLifecycleService,
    account_token_digest,
)
from app.auth.administration import IdentityAdminService
from app.auth.enums import SecurityEventType, UserStatus
from app.auth.models import (
    AccountToken,
    AuthSession,
    PasswordCredential,
    SecurityEvent,
)
from app.auth.throttling import LoginThrottleService, source_digest


NOW = datetime(2026, 7, 25, 20, 0, tzinfo=timezone.utc)
PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "new correct horse battery staple"


def test_hasher() -> PasswordHasher:
    return PasswordHasher(
        time_cost=1,
        memory_cost=8192,
        parallelism=1,
    )


class AccountLifecycleTests(unittest.TestCase):
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

    def test_unnamed_invitation_recipient_chooses_identity_and_cannot_replay(self):
        with Session(self.engine) as db:
            service = AccountLifecycleService(db, password_hasher=test_hasher(), clock=lambda: NOW)
            issued = service.invite_user(self._admin(db), lifetime_minutes=60)
            user_id = issued.user.id
            activated = service.activate(issued.token, PASSWORD, username="Chosen.Player", display_name="My player")
            self.assertEqual(user_id, activated.id)
            self.assertEqual("Chosen.Player", activated.username)
            self.assertEqual("chosen.player", activated.normalized_username)
            self.assertEqual("My player", activated.display_name)
            with self.assertRaises(AccountLifecycleError):
                service.activate(issued.token, PASSWORD, username="Someone.Else")

    def test_activation_username_collision_keeps_invitation_usable(self):
        with Session(self.engine) as db:
            admin = self._admin(db)
            service = AccountLifecycleService(db, password_hasher=test_hasher(), clock=lambda: NOW)
            issued = service.invite_user(admin, lifetime_minutes=60)
            with self.assertRaises(AccountLifecycleError):
                service.activate(issued.token, PASSWORD, username="KEEPER")
            db.rollback()
            self.assertEqual(UserStatus.PENDING, issued.user.status)
            activated = service.activate(issued.token, PASSWORD, username="Available.Player", display_name="Player")
            self.assertEqual(UserStatus.ACTIVE, activated.status)

    def tearDown(self):
        self.engine.dispose()

    def _admin(self, db: Session):
        return IdentityAdminService(
            db,
            password_hasher=test_hasher(),
            clock=lambda: NOW,
        ).create_initial_admin("keeper", PASSWORD)

    def test_invitation_activation_is_one_time_and_digest_backed(self):
        with Session(self.engine) as db:
            admin = self._admin(db)
            service = AccountLifecycleService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: NOW,
                token_factory=lambda size: "activation-secret",
            )
            issued = service.invite_user(
                admin,
                "Player.One",
                display_name="Player One",
                lifetime_minutes=60,
            )

            token = db.exec(select(AccountToken)).one()
            self.assertEqual(
                account_token_digest("activation-secret"),
                token.token_digest,
            )
            self.assertNotIn("activation-secret", token.token_digest)
            self.assertEqual(UserStatus.PENDING, issued.user.status)
            self.assertIsNone(
                db.get(PasswordCredential, issued.user.id)
            )

            activated = service.activate(
                issued.token,
                NEW_PASSWORD,
            )
            self.assertEqual(UserStatus.ACTIVE, activated.status)
            credential = db.get(PasswordCredential, activated.id)
            self.assertTrue(
                service.credentials.verify_password(
                    credential,
                    NEW_PASSWORD,
                )
            )
            with self.assertRaises(AccountLifecycleError):
                service.activate(issued.token, NEW_PASSWORD)
            db.rollback()

            event_types = {
                event.event_type
                for event in db.exec(select(SecurityEvent)).all()
            }
            self.assertIn(SecurityEventType.USER_INVITED, event_types)
            self.assertIn(
                SecurityEventType.ACCOUNT_ACTIVATED,
                event_types,
            )

    def test_password_reset_revokes_sessions_and_rejects_replay(self):
        generated = iter(("activation-token", "reset-token"))
        with Session(self.engine) as db:
            admin = self._admin(db)
            service = AccountLifecycleService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: NOW,
                token_factory=lambda size: next(generated),
            )
            invited = service.invite_user(
                admin,
                "player",
                lifetime_minutes=60,
            )
            user = service.activate(invited.token, PASSWORD)
            auth_session = AuthSession(
                user_id=user.id,
                token_digest="a" * 64,
                csrf_token_digest="b" * 64,
                created_at=NOW,
                last_used_at=NOW,
                expires_at=NOW + timedelta(hours=1),
                absolute_expires_at=NOW + timedelta(days=1),
            )
            db.add(auth_session)
            db.commit()

            reset = service.issue_password_reset(
                admin,
                user.id,
                lifetime_minutes=30,
            )
            service.reset_password(reset.token, NEW_PASSWORD)
            db.refresh(auth_session)

            self.assertIsNotNone(auth_session.revoked_at)
            with self.assertRaises(AccountLifecycleError):
                service.reset_password(reset.token, PASSWORD)

    def test_expired_token_and_non_admin_issuance_are_rejected(self):
        current_time = [NOW]
        with Session(self.engine) as db:
            admin = self._admin(db)
            service = AccountLifecycleService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: current_time[0],
                token_factory=lambda size: "expiring-token",
            )
            invited = service.invite_user(
                admin,
                "player",
                lifetime_minutes=5,
            )
            current_time[0] = NOW + timedelta(minutes=6)
            with self.assertRaises(AccountLifecycleError):
                service.activate(invited.token, PASSWORD)
            db.rollback()

            with self.assertRaises(AccountLifecycleError):
                service.invite_user(
                    invited.user,
                    "other-player",
                    lifetime_minutes=5,
                )

    def test_deletion_tombstones_user_and_removes_credentials(self):
        generated = iter((
            "activation-token",
            "replacement-activation-token",
        ))
        with Session(self.engine) as db:
            admin = self._admin(db)
            service = AccountLifecycleService(
                db,
                password_hasher=test_hasher(),
                clock=lambda: NOW,
                token_factory=lambda size: next(generated),
            )
            invited = service.invite_user(
                admin,
                "player",
                lifetime_minutes=60,
            )
            user = service.activate(invited.token, PASSWORD)

            deleted = service.delete_user(admin, user.id)

            self.assertEqual(UserStatus.DELETED, deleted.status)
            self.assertFalse(deleted.can_login)
            self.assertIsNotNone(deleted.deleted_at)
            self.assertIsNone(db.get(PasswordCredential, deleted.id))
            self.assertEqual(f"Deleted user {deleted.id}", deleted.username)
            self.assertEqual(
                f"_deleted_user_{deleted.id}",
                deleted.normalized_username,
            )

            # Simulate a tombstone created by an older application version.
            deleted.username = "player"
            deleted.normalized_username = "player"
            db.add(deleted)
            db.commit()

            replacement_invitation = service.invite_user(
                admin,
                lifetime_minutes=60,
            )
            replacement = service.activate(
                replacement_invitation.token,
                PASSWORD,
                username="PLAYER",
                display_name="Replacement player",
            )
            self.assertNotEqual(deleted.id, replacement.id)
            self.assertEqual("player", replacement.normalized_username)


class LoginThrottleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_source_throttle_locks_resets_and_uses_keyed_digest(self):
        current_time = [NOW]
        with Session(self.engine) as db:
            service = LoginThrottleService(
                db,
                failure_limit=3,
                window_seconds=60,
                lock_seconds=30,
                clock=lambda: current_time[0],
            )
            digest = source_digest("192.0.2.10", "s" * 32)

            self.assertNotIn("192.0.2.10", digest)
            self.assertNotEqual(
                digest,
                source_digest("192.0.2.10", "t" * 32),
            )
            self.assertFalse(service.record_failure(digest))
            self.assertFalse(service.record_failure(digest))
            self.assertTrue(service.record_failure(digest))
            self.assertFalse(service.is_allowed(digest))

            current_time[0] = NOW + timedelta(seconds=31)
            self.assertTrue(service.is_allowed(digest))
            service.record_success(digest)
            self.assertTrue(service.is_allowed(digest))


if __name__ == "__main__":
    unittest.main()
