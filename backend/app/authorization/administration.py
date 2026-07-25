from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth.enums import SecurityEventType, SystemRole, UserStatus
from app.auth.events import SecurityEventService
from app.auth.models import User
from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignRole
from app.authorization.models import CampaignMembership


class CampaignAuthorizationAdminService:
    """Explicit, audited system-administrator campaign recovery."""

    def __init__(self, db: Session, actor: User):
        self.db = db
        self.actor = actor
        self.events = SecurityEventService(db)

    def inspect(
        self,
        campaign_id: int,
        reason: str,
    ) -> CampaignContext:
        return CampaignContext.resolve_elevated(
            self.db,
            campaign_id,
            self.actor,
            reason=reason,
        )

    def recover(
        self,
        campaign_id: int,
        owner_user_id: int,
        reason: str,
    ) -> CampaignContext:
        context = self.inspect(campaign_id, reason)
        owner = self.db.get(User, owner_user_id)
        if (
            owner is None
            or owner.status is not UserStatus.ACTIVE
            or not owner.can_login
            or owner.system_role is SystemRole.CUSTODIAN
        ):
            raise HTTPException(
                status_code=404,
                detail="Recovery owner not found",
            )
        membership = self.db.exec(
            select(CampaignMembership).where(
                CampaignMembership.campaign_id == campaign_id,
                CampaignMembership.user_id == owner_user_id,
            )
        ).first()
        if membership is None:
            membership = CampaignMembership(
                campaign_id=campaign_id,
                user_id=owner_user_id,
                role=CampaignRole.OWNER,
            )
        else:
            membership.role = CampaignRole.OWNER
            membership.is_custodial = False
        custodial_memberships = self.db.exec(
            select(CampaignMembership).where(
                CampaignMembership.campaign_id == campaign_id,
                CampaignMembership.is_custodial.is_(True),
            )
        ).all()
        for custodial in custodial_memberships:
            self.db.delete(custodial)
        context.campaign.orphaned = False
        self.db.add(membership)
        self.db.add(context.campaign)
        self.events.record(
            SecurityEventType.CAMPAIGN_RECOVERED,
            user_id=owner_user_id,
            actor_user_id=self.actor.id,
            campaign_id=campaign_id,
            reason=reason.strip(),
            used_elevation=True,
        )
        self.db.commit()
        return context
