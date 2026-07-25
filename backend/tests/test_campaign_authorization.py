import unittest

from fastapi import FastAPI, HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth.accounts import AccountLifecycleService
from app.auth.enums import (
    SecurityEventType,
    SystemRole,
    UserStatus,
)
from app.auth.models import SecurityEvent, User
from app.authorization.administration import (
    CampaignAuthorizationAdminService,
)
from app.authorization.capabilities import ROLE_CAPABILITIES
from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignCapability, CampaignRole
from app.authorization.memberships import CampaignMembershipService
from app.authorization.models import CampaignMembership
from app.authorization.route_audit import (
    audit_campaign_route_authorization,
)
from app.models.api import CharacterCreate, CharacterUpdate, PersonData
from app.models.database import Campaign
from app.services.campaigns import CampaignService
from app.services.characters import CharacterService
from tests.authorization_helpers import campaign_context, create_user


class CampaignAuthorizationTests(unittest.TestCase):
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

    def test_role_matrix_keeps_owner_only_campaign_privileges(self):
        owner = ROLE_CAPABILITIES[CampaignRole.OWNER]
        member = ROLE_CAPABILITIES[CampaignRole.MEMBER]
        viewer = ROLE_CAPABILITIES[CampaignRole.VIEWER]

        self.assertIn(CampaignCapability.CAMPAIGN_EXPORT, owner)
        self.assertIn(CampaignCapability.MEMBERSHIP_MANAGE, owner)
        self.assertNotIn(CampaignCapability.CAMPAIGN_EXPORT, member)
        self.assertNotIn(CampaignCapability.MEMBERSHIP_MANAGE, member)
        self.assertIn(CampaignCapability.SHARED_RESOURCE_WRITE, member)
        self.assertNotIn(CampaignCapability.SHARED_RESOURCE_WRITE, viewer)

    def test_nonmember_is_hidden_and_viewer_mutation_is_forbidden(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Private")
            db.add(campaign)
            db.flush()
            owner_context = campaign_context(db, campaign)
            outsider = create_user(db)
            viewer = create_user(db)
            viewer_membership = CampaignMembership(
                campaign_id=campaign.id,
                user_id=viewer.id,
                role=CampaignRole.VIEWER,
            )
            db.add(viewer_membership)
            db.commit()

            with self.assertRaises(HTTPException) as hidden:
                CampaignContext.resolve(db, campaign.id, outsider)
            self.assertEqual(404, hidden.exception.status_code)

            viewer_context = CampaignContext.resolve(
                db,
                campaign.id,
                viewer,
            )
            with self.assertRaises(HTTPException) as forbidden:
                viewer_context.require(
                    CampaignCapability.SHARED_RESOURCE_WRITE
                )
            self.assertEqual(403, forbidden.exception.status_code)
            self.assertTrue(
                owner_context.can(CampaignCapability.CAMPAIGN_DELETE)
            )

    def test_campaign_creation_and_listing_are_membership_scoped(self):
        with Session(self.engine) as db:
            first_user = create_user(db)
            second_user = create_user(db)
            first = CampaignService(db, first_user)
            second = CampaignService(db, second_user)

            created = first.create(name="First user's campaign")

            self.assertEqual([created.id], [item.id for item in first.list_reads()])
            self.assertEqual([], second.list_reads())
            membership = db.exec(
                select(CampaignMembership).where(
                    CampaignMembership.campaign_id == created.id,
                    CampaignMembership.user_id == first_user.id,
                )
            ).one()
            self.assertEqual(CampaignRole.OWNER, membership.role)

    def test_last_human_owner_cannot_leave_or_be_demoted(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Owned")
            db.add(campaign)
            db.flush()
            context = campaign_context(db, campaign)
            service = CampaignMembershipService(context)

            with self.assertRaises(HTTPException) as leave_error:
                service.leave()
            self.assertEqual(409, leave_error.exception.status_code)

            with self.assertRaises(HTTPException) as role_error:
                service.change_role(
                    context.user.id,
                    CampaignRole.MEMBER,
                )
            self.assertEqual(409, role_error.exception.status_code)

    def test_member_can_write_only_the_assigned_character(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Characters")
            db.add(campaign)
            db.flush()
            owner_context = campaign_context(db, campaign)
            characters = CharacterService(owner_context)
            first = characters.create(
                CharacterCreate(person=PersonData(name="Assigned"))
            )
            second = characters.create(
                CharacterCreate(
                    person=PersonData(name="Other"),
                    make_active=False,
                )
            )
            member = create_user(db)
            CampaignMembershipService(owner_context).add_user(
                member.username,
                CampaignRole.MEMBER,
            )
            CampaignMembershipService(owner_context).assign_character(
                owner_context.user.id,
                None,
            )
            CampaignMembershipService(owner_context).assign_character(
                member.id,
                first.person.id,
            )
            member_context = CampaignContext.resolve(
                db,
                campaign.id,
                member,
            )
            campaign_read = CampaignService(db, member).get_read(campaign.id)
            self.assertEqual(
                first.person.id,
                campaign_read.assigned_character_person_id,
            )
            self.assertEqual(
                CampaignRole.MEMBER,
                campaign_read.membership_role,
            )
            member_characters = CharacterService(member_context)

            updated = member_characters.update(
                first.person.id,
                CharacterUpdate(
                    person=PersonData(name="Assigned Updated"),
                ),
            )
            self.assertEqual("Assigned Updated", updated.person.name)
            with self.assertRaises(HTTPException) as forbidden:
                member_characters.update(
                    second.person.id,
                    CharacterUpdate(
                        person=PersonData(name="Other Updated"),
                    ),
                )
            self.assertEqual(403, forbidden.exception.status_code)

    def test_deleting_sole_owner_assigns_nonlogin_custody(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            owner = create_user(db)
            custodian = create_user(
                db,
                role=SystemRole.CUSTODIAN,
                can_login=False,
            )
            campaign = Campaign(name="Preserved")
            db.add(campaign)
            db.flush()
            db.add(
                CampaignMembership(
                    campaign_id=campaign.id,
                    user_id=owner.id,
                    role=CampaignRole.OWNER,
                )
            )
            db.commit()

            AccountLifecycleService(db).delete_user(admin, owner.id)

            db.refresh(campaign)
            db.refresh(owner)
            self.assertTrue(campaign.orphaned)
            self.assertEqual(UserStatus.DELETED, owner.status)
            custody = db.exec(
                select(CampaignMembership).where(
                    CampaignMembership.campaign_id == campaign.id
                )
            ).one()
            self.assertEqual(custodian.id, custody.user_id)
            self.assertTrue(custody.is_custodial)
            self.assertEqual(CampaignRole.OWNER, custody.role)

    def test_admin_elevation_is_explicit_audited_and_recoverable(self):
        with Session(self.engine) as db:
            admin = create_user(db, role=SystemRole.ADMIN)
            new_owner = create_user(db)
            custodian = create_user(
                db,
                role=SystemRole.CUSTODIAN,
                can_login=False,
            )
            campaign = Campaign(name="Orphaned", orphaned=True)
            db.add(campaign)
            db.flush()
            db.add(
                CampaignMembership(
                    campaign_id=campaign.id,
                    user_id=custodian.id,
                    role=CampaignRole.OWNER,
                    is_custodial=True,
                )
            )
            db.commit()
            service = CampaignAuthorizationAdminService(db, admin)

            elevated = service.inspect(
                campaign.id,
                "Investigate owner loss",
            )
            self.assertTrue(elevated.elevated)
            self.assertIsNone(elevated.membership)

            service.recover(
                campaign.id,
                new_owner.id,
                "Verified replacement owner",
            )
            db.refresh(campaign)
            self.assertFalse(campaign.orphaned)
            membership = db.exec(
                select(CampaignMembership).where(
                    CampaignMembership.campaign_id == campaign.id
                )
            ).one()
            self.assertEqual(new_owner.id, membership.user_id)
            event_types = set(
                db.exec(select(SecurityEvent.event_type)).all()
            )
            self.assertIn(
                SecurityEventType.ADMIN_CAMPAIGN_ELEVATION,
                event_types,
            )
            self.assertIn(
                SecurityEventType.CAMPAIGN_RECOVERED,
                event_types,
            )

    def test_route_audit_rejects_unclassified_campaign_route(self):
        application = FastAPI()

        @application.get("/api/campaigns/{campaign_id}/unsafe")
        def unsafe_route(campaign_id: int):
            return {"campaign_id": campaign_id}

        with self.assertRaises(RuntimeError):
            audit_campaign_route_authorization(application)


if __name__ == "__main__":
    unittest.main()
