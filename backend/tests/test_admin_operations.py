from datetime import datetime, timezone
import unittest

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth.admin_operations import (
    IdentityAdminOperationsError,
    IdentityAdminOperationsService,
)
from app.auth.enums import SystemRole, UserStatus
from app.auth.models import AuthSession, SecurityEvent
from app.auth.sessions import AuthSessionService
from app.authorization.enums import CampaignRole
from app.authorization.models import CampaignMembership
from app.models.database import Campaign
from tests.authorization_helpers import create_user


class IdentityAdminOperationsTests(unittest.TestCase):
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

    def test_role_change_is_admin_only_audited_and_revokes_sessions(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            member = create_user(db)
            AuthSessionService(db).create(member)
            db.commit()
            with self.assertRaises(IdentityAdminOperationsError):
                IdentityAdminOperationsService(db, member).set_role(member.id, SystemRole.ADMIN, "Escalate")
            db.rollback()
            service = IdentityAdminOperationsService(db, admin)
            with self.assertRaises(IdentityAdminOperationsError):
                service.set_role(member.id, SystemRole.ADMIN, " ")
            db.rollback()
            changed, revoked = service.set_role(member.id, SystemRole.ADMIN, "Help administer server")
            self.assertEqual(SystemRole.ADMIN, changed.system_role)
            self.assertEqual(1, revoked)
            self.assertTrue(any("system_role_changed:admin" in event.reason
                for event in db.exec(select(SecurityEvent)).all()))
            with self.assertRaises(IdentityAdminOperationsError):
                service.set_role(admin.id, SystemRole.USER, "Self demotion")
            db.rollback()
            changed, _ = service.set_role(member.id, SystemRole.USER, "End admin duties")
            self.assertEqual(SystemRole.USER, changed.system_role)

    def test_role_change_rejects_custodian_and_inactive_accounts(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            targets = [create_user(db, role=SystemRole.CUSTODIAN, can_login=False),
                       create_user(db, status=UserStatus.PENDING),
                       create_user(db, status=UserStatus.SUSPENDED),
                       create_user(db, can_login=False)]
            db.commit()
            service = IdentityAdminOperationsService(db, admin)
            for target in targets:
                with self.assertRaises(IdentityAdminOperationsError):
                    service.set_role(target.id, SystemRole.ADMIN, "Test")
                db.rollback()

    def tearDown(self):
        self.engine.dispose()

    def test_lists_users_with_session_and_membership_counts(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            member = create_user(db)
            campaign = Campaign(name="Shared")
            db.add(campaign)
            db.flush()
            db.add(
                CampaignMembership(
                    campaign_id=campaign.id,
                    user_id=member.id,
                    role=CampaignRole.MEMBER,
                )
            )
            AuthSessionService(db).create(member)
            db.commit()

            rows = IdentityAdminOperationsService(
                db, admin
            ).list_users()
            member_row = next(row for row in rows if row[0].id == member.id)
            self.assertEqual(1, member_row[1])
            self.assertEqual(1, member_row[2])

    def test_suspending_user_revokes_sessions_and_is_audited(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            member = create_user(db)
            AuthSessionService(db).create(member)
            AuthSessionService(db).create(member)
            db.commit()

            updated, revoked = IdentityAdminOperationsService(
                db, admin
            ).set_status(member.id, UserStatus.SUSPENDED, "Compromised")

            self.assertEqual(UserStatus.SUSPENDED, updated.status)
            self.assertEqual(2, revoked)
            sessions = db.exec(
                select(AuthSession).where(AuthSession.user_id == member.id)
            ).all()
            self.assertTrue(all(item.revoked_at for item in sessions))
            audit = db.exec(
                select(SecurityEvent).where(
                    SecurityEvent.user_id == member.id
                )
            ).one()
            self.assertIn("account_status_changed:suspended", audit.reason)
            self.assertIn("Compromised", audit.reason)

    def test_admin_cannot_suspend_self_or_custodian(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            custodian = create_user(
                db,
                role=SystemRole.CUSTODIAN,
                can_login=False,
            )
            service = IdentityAdminOperationsService(db, admin)

            for user in (admin, custodian):
                with self.subTest(user=user.system_role):
                    with self.assertRaises(
                        IdentityAdminOperationsError
                    ):
                        service.set_status(
                            user.id,
                            UserStatus.SUSPENDED,
                            "Test",
                        )
                    db.rollback()

    def test_global_revocation_includes_admin_session(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            member = create_user(db)
            AuthSessionService(db).create(admin)
            AuthSessionService(db).create(member)
            db.commit()

            revoked = IdentityAdminOperationsService(
                db, admin
            ).revoke_all_sessions("Incident response")

            self.assertEqual(2, revoked)
            active = db.exec(
                select(AuthSession).where(AuthSession.revoked_at.is_(None))
            ).all()
            self.assertEqual([], active)


if __name__ == "__main__":
    unittest.main()
