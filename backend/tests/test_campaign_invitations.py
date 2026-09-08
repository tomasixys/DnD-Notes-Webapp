from datetime import datetime, timedelta, timezone
import unittest

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.requests import Request

from app.auth.accounts import AccountLifecycleService
from app.auth.enums import SystemRole, UserStatus
from app.auth.models import SecurityEvent
from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignCapability, CampaignRole
from app.authorization.invitations import (
    CampaignInvitationError,
    CampaignInvitationService,
    invitation_token_digest,
)
from app.authorization.memberships import CampaignMembershipService
from app.authorization.models import (
    CampaignInvitation,
    CampaignMembership,
)
from app.authorization.schemas import CampaignInvitationAccept
from app.config import ApplicationSettings
from app.models.database import Campaign
from app.routers.invitations import accept_campaign_invitation
from app.main import app
from app.services.campaigns import CampaignService
from tests.authorization_helpers import campaign_context, create_user


NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


class CampaignInvitationTests(unittest.TestCase):
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

    def test_inbox_acceptance_requires_recipient_and_is_single_use(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Inbox")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            invited, outsider = create_user(db), create_user(db)
            issued = CampaignInvitationService(db, owner.user).issue(
                owner, invited.username, CampaignRole.MEMBER, lifetime_minutes=60,
            )
            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(db, outsider).accept(invitation_id=issued.invitation.id)
            db.rollback()
            accepted = CampaignInvitationService(db, invited).accept(invitation_id=issued.invitation.id)
            self.assertEqual(invited.id, accepted.membership.user_id)
            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(db, invited).accept(invitation_id=issued.invitation.id)

    def test_decline_hides_invitation_and_prevents_link_or_inbox_acceptance(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Inbox")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            invited, outsider = create_user(db), create_user(db)
            issued = CampaignInvitationService(db, owner.user).issue(
                owner, invited.username, CampaignRole.MEMBER, lifetime_minutes=60,
            )
            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(db, outsider).decline(issued.invitation.id)
            db.rollback()
            service = CampaignInvitationService(db, invited)
            service.decline(issued.invitation.id)
            self.assertEqual([], service.list_pending())
            for kwargs in ({"invitation_id": issued.invitation.id}, {"raw_token": issued.token}):
                with self.assertRaises(CampaignInvitationError):
                    service.accept(**kwargs)
                db.rollback()

    def test_expired_inbox_invitation_cannot_be_accepted(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Expired")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            invited = create_user(db)
            issued = CampaignInvitationService(db, owner.user, clock=lambda: NOW).issue(
                owner, invited.username, CampaignRole.MEMBER, lifetime_minutes=1,
            )
            service = CampaignInvitationService(db, invited, clock=lambda: NOW + timedelta(minutes=2))
            with self.assertRaises(CampaignInvitationError):
                service.accept(invitation_id=issued.invitation.id)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def request(source: str = "203.0.113.7") -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/campaign-invitations/accept",
                "headers": [],
                "client": (source, 443),
                "server": ("notes.example.test", 443),
                "scheme": "https",
                "query_string": b"",
            }
        )

    def test_invitation_is_digest_backed_and_acceptance_is_atomic(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Shared")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            invited = create_user(db)
            outsider = create_user(db)
            service = CampaignInvitationService(
                db,
                owner.user,
                clock=lambda: NOW,
                token_factory=lambda size: "campaign-secret",
            )

            issued = service.issue(
                owner,
                invited.username,
                CampaignRole.MEMBER,
                lifetime_minutes=60,
            )
            invitation = db.get(
                CampaignInvitation,
                issued.invitation.id,
            )

            self.assertEqual("campaign-secret", issued.token)
            self.assertEqual(
                invitation_token_digest("campaign-secret"),
                invitation.token_digest,
            )
            self.assertNotIn("campaign-secret", invitation.token_digest)
            self.assertEqual(
                [issued.invitation.id],
                [
                    pending.id
                    for pending in CampaignInvitationService(
                        db,
                        invited,
                        clock=lambda: NOW,
                    ).list_pending()
                ],
            )

            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(
                    db,
                    outsider,
                    clock=lambda: NOW,
                ).accept("campaign-secret")

            accepted = CampaignInvitationService(
                db,
                invited,
                clock=lambda: NOW,
            ).accept("campaign-secret")
            self.assertEqual(
                CampaignRole.MEMBER,
                accepted.membership.role,
            )
            self.assertIsNotNone(
                db.exec(
                    select(CampaignMembership).where(
                        CampaignMembership.campaign_id == campaign.id,
                        CampaignMembership.user_id == invited.id,
                    )
                ).first()
            )
            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(
                    db,
                    invited,
                    clock=lambda: NOW,
                ).accept("campaign-secret")

            event_reasons = set(
                db.exec(select(SecurityEvent.reason)).all()
            )
            self.assertTrue(
                any(
                    reason
                    and reason.startswith("action=invitation_created")
                    for reason in event_reasons
                )
            )
            self.assertTrue(
                any(
                    reason
                    and reason.startswith("action=invitation_accepted")
                    for reason in event_reasons
                )
            )

    def test_pending_account_must_activate_before_acceptance(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Pending")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            invited = create_user(db, status=UserStatus.PENDING)
            issued = CampaignInvitationService(
                db,
                owner.user,
                clock=lambda: NOW,
                token_factory=lambda size: "pending-secret",
            ).issue(
                owner,
                invited.username,
                CampaignRole.VIEWER,
                lifetime_minutes=60,
            )

            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(
                    db,
                    invited,
                    clock=lambda: NOW,
                ).accept(issued.token)

            invited.status = UserStatus.ACTIVE
            db.add(invited)
            db.commit()
            accepted = CampaignInvitationService(
                db,
                invited,
                clock=lambda: NOW,
            ).accept(issued.token)
            self.assertEqual(CampaignRole.VIEWER, accepted.membership.role)
            invited_context = CampaignContext.resolve(
                db,
                campaign.id,
                invited,
            )
            self.assertTrue(
                invited_context.can(
                    CampaignCapability.SHARED_RESOURCE_READ
                )
            )
            self.assertFalse(
                invited_context.can(
                    CampaignCapability.SHARED_RESOURCE_WRITE
                )
            )

    def test_replacement_revocation_and_expiry_invalidate_tokens(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Lifecycle")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            invited = create_user(db)
            generated = iter(("first-token", "second-token"))
            service = CampaignInvitationService(
                db,
                owner.user,
                clock=lambda: NOW,
                token_factory=lambda size: next(generated),
            )
            first = service.issue(
                owner,
                invited.username,
                CampaignRole.MEMBER,
                lifetime_minutes=60,
            )
            second = service.replace(
                owner,
                first.invitation.id,
                lifetime_minutes=60,
            )

            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(
                    db,
                    invited,
                    clock=lambda: NOW,
                ).accept(first.token)

            revoked = service.revoke(owner, second.invitation.id)
            self.assertEqual("revoked", revoked.status.value)
            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(
                    db,
                    invited,
                    clock=lambda: NOW,
                ).accept(second.token)

            audit_reasons = set(
                db.exec(select(SecurityEvent.reason)).all()
            )
            self.assertTrue(
                any(
                    reason
                    and reason.startswith("action=invitation_replaced")
                    for reason in audit_reasons
                )
            )
            self.assertIn(
                "action=invitation_revoked",
                audit_reasons,
            )

            invitation = db.get(
                CampaignInvitation,
                second.invitation.id,
            )
            invitation.revoked_at = None
            invitation.expires_at = NOW - timedelta(seconds=1)
            db.add(invitation)
            db.commit()
            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(
                    db,
                    invited,
                    clock=lambda: NOW,
                ).accept(second.token)

    def test_member_cannot_issue_campaign_invitation(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Owner only")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            member = create_user(db)
            invited = create_user(db)
            membership = CampaignMembership(
                campaign_id=campaign.id,
                user_id=member.id,
                role=CampaignRole.MEMBER,
            )
            db.add(membership)
            db.commit()
            member_context = CampaignContext(
                db,
                campaign,
                member,
                membership,
            )

            with self.assertRaises(HTTPException) as forbidden:
                CampaignInvitationService(db, member).issue(
                    member_context,
                    invited.username,
                    CampaignRole.MEMBER,
                    lifetime_minutes=60,
                )
            self.assertEqual(403, forbidden.exception.status_code)
            self.assertEqual(
                [],
                CampaignInvitationService(
                    db,
                    owner.user,
                ).list_for_campaign(owner),
            )

    def test_account_deletion_revokes_unaccepted_invitations(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            create_user(
                db,
                role=SystemRole.CUSTODIAN,
                can_login=False,
            )
            campaign = Campaign(name="Deletion")
            db.add(campaign)
            db.flush()
            owner_user = create_user(db)
            owner = campaign_context(
                db,
                campaign,
                user=owner_user,
            )
            invited = create_user(db)
            issued = CampaignInvitationService(
                db,
                owner.user,
                clock=lambda: NOW,
                token_factory=lambda size: "deleted-owner-token",
            ).issue(
                owner,
                invited.username,
                CampaignRole.MEMBER,
                lifetime_minutes=60,
            )

            AccountLifecycleService(
                db,
                clock=lambda: NOW,
            ).delete_user(admin, owner.user.id)

            invitation = db.get(
                CampaignInvitation,
                issued.invitation.id,
            )
            self.assertIsNotNone(invitation.revoked_at)
            with self.assertRaises(CampaignInvitationError):
                CampaignInvitationService(
                    db,
                    invited,
                    clock=lambda: NOW,
                ).accept(issued.token)

    def test_acceptance_failures_are_source_rate_limited(self):
        settings = ApplicationSettings.model_validate(
            {
                "security": {
                    "invitation_failure_limit": 3,
                    "invitation_failure_window_seconds": 300,
                    "invitation_lock_seconds": 300,
                }
            }
        )
        with Session(self.engine) as db:
            user = create_user(db)
            db.commit()
            payload = CampaignInvitationAccept(token="invalid-token")

            for _ in range(3):
                with self.assertRaises(HTTPException) as invalid:
                    accept_campaign_invitation(
                        payload,
                        self.request(),
                        settings,
                        "s" * 32,
                        user,
                        db,
                    )
                self.assertEqual(400, invalid.exception.status_code)

            with self.assertRaises(HTTPException) as throttled:
                accept_campaign_invitation(
                    payload,
                    self.request(),
                    settings,
                    "s" * 32,
                    user,
                    db,
                )
            self.assertEqual(429, throttled.exception.status_code)

    def test_ownership_transfer_is_atomic_and_audited(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Transfer")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            member = create_user(db)
            membership = CampaignMembership(
                campaign_id=campaign.id,
                user_id=member.id,
                role=CampaignRole.VIEWER,
            )
            db.add(membership)
            db.commit()

            transferred = CampaignMembershipService(
                owner
            ).transfer_ownership(member.id)

            self.assertEqual(
                CampaignRole.MEMBER,
                transferred.previous_owner.role,
            )
            self.assertEqual(
                CampaignRole.OWNER,
                transferred.new_owner.role,
            )
            event = db.exec(
                select(SecurityEvent).where(
                    SecurityEvent.reason.startswith(
                        "action=ownership_transferred"
                    )
                )
            ).one()
            self.assertEqual(owner.user.id, event.actor_user_id)
            self.assertEqual(member.id, event.user_id)

    def test_role_removal_and_campaign_deletion_are_audited(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Audited")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            member = create_user(db)
            db.add(
                CampaignMembership(
                    campaign_id=campaign.id,
                    user_id=member.id,
                    role=CampaignRole.MEMBER,
                )
            )
            db.commit()
            service = CampaignMembershipService(owner)

            service.change_role(member.id, CampaignRole.VIEWER)
            service.remove_user(member.id)
            CampaignService(db, owner.user).delete(owner)

            reasons = set(
                db.exec(select(SecurityEvent.reason)).all()
            )
            self.assertIn(
                "action=role_changed role=viewer",
                reasons,
            )
            self.assertIn("action=member_removed", reasons)
            self.assertIn("action=campaign_deleted", reasons)

    def test_direct_membership_creation_route_is_removed(self):
        schema = app.openapi()
        member_collection = schema["paths"][
            "/api/campaigns/{campaign_id}/members"
        ]

        self.assertIn("get", member_collection)
        self.assertNotIn("post", member_collection)
        self.assertIn(
            "post",
            schema["paths"][
                "/api/campaigns/{campaign_id}/invitations"
            ],
        )


if __name__ == "__main__":
    unittest.main()
