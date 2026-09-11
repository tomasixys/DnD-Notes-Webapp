import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth.enums import SystemRole
from app.authorization.enums import CampaignRole
from app.authorization.models import CampaignInvitation
from app.authorization.route_audit import audit_campaign_route_authorization
from app.models.database import Campaign, IssueReport
from app.models.enums import IssueStatus
from app.routers import notifications
from app.services.notifications import AccountNotificationService
from tests.authorization_helpers import create_user


NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


class AccountNotificationServiceTests(unittest.TestCase):
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

    @staticmethod
    def add_invitation(
        db: Session,
        *,
        user_id: int,
        campaign_name: str,
        token: str,
        expires_at: datetime,
        accepted: bool = False,
        orphaned: bool = False,
    ) -> None:
        campaign = Campaign(name=campaign_name, orphaned=orphaned)
        db.add(campaign)
        db.flush()
        db.add(CampaignInvitation(
            campaign_id=campaign.id,
            invited_user_id=user_id,
            role=CampaignRole.MEMBER,
            token_digest=token,
            expires_at=expires_at,
            accepted_at=NOW if accepted else None,
        ))

    def test_summary_only_counts_actionable_items_for_current_user(self):
        with Session(self.engine) as db:
            user = create_user(db)
            other = create_user(db)
            admin = create_user(db, role=SystemRole.ADMIN)
            self.add_invitation(
                db,
                user_id=user.id,
                campaign_name="Pending campaign",
                token="pending",
                expires_at=NOW + timedelta(days=1),
            )
            self.add_invitation(
                db,
                user_id=user.id,
                campaign_name="Expired campaign",
                token="expired",
                expires_at=NOW - timedelta(seconds=1),
            )
            self.add_invitation(
                db,
                user_id=user.id,
                campaign_name="Accepted campaign",
                token="accepted",
                expires_at=NOW + timedelta(days=1),
                accepted=True,
            )
            self.add_invitation(
                db,
                user_id=user.id,
                campaign_name="Orphaned campaign",
                token="orphaned",
                expires_at=NOW + timedelta(days=1),
                orphaned=True,
            )
            self.add_invitation(
                db,
                user_id=other.id,
                campaign_name="Someone else's campaign",
                token="other",
                expires_at=NOW + timedelta(days=1),
            )
            db.add(IssueReport(
                title="Pending report",
                description="An administrator needs to review this report.",
                reporter_user_id=user.id,
                status=IssueStatus.PENDING,
            ))
            db.add(IssueReport(
                title="Acknowledged report",
                description="This report has already been reviewed.",
                reporter_user_id=user.id,
                status=IssueStatus.ACKNOWLEDGED,
                reviewed_at=NOW,
            ))
            db.commit()

            user_summary = AccountNotificationService(
                db,
                user,
                clock=lambda: NOW,
            ).summary()
            admin_summary = AccountNotificationService(
                db,
                admin,
                clock=lambda: NOW,
            ).summary()

            self.assertEqual(1, user_summary.pending_campaign_invitations)
            self.assertEqual(0, user_summary.pending_issue_reports)
            self.assertEqual(0, admin_summary.pending_campaign_invitations)
            self.assertEqual(1, admin_summary.pending_issue_reports)

    def test_notification_route_passes_authentication_audit(self):
        application = FastAPI()
        application.include_router(notifications.router)
        audit_campaign_route_authorization(application)


if __name__ == "__main__":
    unittest.main()
