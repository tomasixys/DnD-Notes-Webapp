from dataclasses import dataclass

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth.enums import SecurityEventType, SystemRole, UserStatus
from app.auth.events import SecurityEventService
from app.auth.models import User
from app.authorization.capabilities import role_has_capability
from app.authorization.enums import CampaignCapability, CampaignRole
from app.authorization.models import CampaignMembership
from app.models.database import Campaign


@dataclass
class CampaignContext:
    """One authenticated user's authorized view of a campaign."""

    db: Session
    campaign: Campaign
    user: User
    membership: CampaignMembership | None
    elevated: bool = False
    client_instance_id: str | None = None

    def __post_init__(self) -> None:
        if (
            self.campaign.id is None
            or self.user.id is None
            or (
                self.membership is not None
                and self.membership.id is None
            )
        ):
            raise ValueError(
                "CampaignContext requires flushed campaign, user, and "
                "membership records"
            )
        if self.membership is not None and (
            self.membership.campaign_id != self.campaign.id
            or self.membership.user_id != self.user.id
        ):
            raise ValueError(
                "CampaignContext membership does not match its campaign "
                "and user"
            )

    @property
    def campaign_id(self) -> int:
        return self.campaign.id

    @property
    def active_character_person_id(self) -> int | None:
        return (
            self.membership.active_character_person_id
            if self.membership is not None
            else None
        )

    @active_character_person_id.setter
    def active_character_person_id(self, person_id: int | None) -> None:
        if self.membership is None:
            raise RuntimeError(
                "Elevated contexts do not have an active character"
            )
        self.membership.active_character_person_id = person_id

    def can(self, capability: CampaignCapability) -> bool:
        return self.elevated or (
            self.membership is not None
            and role_has_capability(self.membership.role, capability)
        )

    def require(self, capability: CampaignCapability) -> None:
        if not self.can(capability):
            raise HTTPException(
                status_code=403,
                detail="Campaign permission denied",
            )

    def can_write_character(self, person_id: int) -> bool:
        return self.elevated or (
            self.membership is not None
            and (
                self.membership.role is CampaignRole.OWNER
                or (
                    self.can(
                        CampaignCapability.ASSIGNED_CHARACTER_WRITE
                    )
                    and self.membership.assigned_character_person_id
                    == person_id
                )
            )
        )

    def require_character_write(self, person_id: int) -> None:
        if not self.can_write_character(person_id):
            raise HTTPException(
                status_code=403,
                detail="Character permission denied",
            )

    @classmethod
    def resolve(
        cls,
        db: Session,
        campaign_id: int,
        user: User,
    ) -> "CampaignContext":
        row = db.exec(
            select(Campaign, CampaignMembership)
            .join(
                CampaignMembership,
                CampaignMembership.campaign_id == Campaign.id,
            )
            .where(
                Campaign.id == campaign_id,
                CampaignMembership.user_id == user.id,
                Campaign.orphaned.is_(False),
            )
        ).first()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Campaign not found",
            )
        campaign, membership = row
        return cls(
            db=db,
            campaign=campaign,
            user=user,
            membership=membership,
        )

    @classmethod
    def resolve_elevated(
        cls,
        db: Session,
        campaign_id: int,
        user: User,
        *,
        reason: str,
    ) -> "CampaignContext":
        normalized_reason = reason.strip()
        if (
            user.status is not UserStatus.ACTIVE
            or not user.can_login
            or user.system_role is not SystemRole.ADMIN
        ):
            SecurityEventService(db).record(
                SecurityEventType.ADMIN_CAMPAIGN_ELEVATION,
                actor_user_id=user.id,
                campaign_id=campaign_id,
                reason=normalized_reason or None,
                outcome="forbidden",
                used_elevation=True,
            )
            db.commit()
            raise HTTPException(
                status_code=403,
                detail="System administrator privileges are required",
            )
        if not normalized_reason:
            SecurityEventService(db).record(
                SecurityEventType.ADMIN_CAMPAIGN_ELEVATION,
                actor_user_id=user.id,
                campaign_id=campaign_id,
                outcome="reason_required",
                used_elevation=True,
            )
            db.commit()
            raise HTTPException(
                status_code=422,
                detail="An elevation reason is required",
            )
        campaign = db.get(Campaign, campaign_id)
        outcome = "succeeded" if campaign is not None else "not_found"
        SecurityEventService(db).record(
            SecurityEventType.ADMIN_CAMPAIGN_ELEVATION,
            actor_user_id=user.id,
            campaign_id=campaign_id,
            reason=normalized_reason,
            outcome=outcome,
            used_elevation=True,
        )
        db.commit()
        if campaign is None:
            raise HTTPException(
                status_code=404,
                detail="Campaign not found",
            )
        return cls(
            db=db,
            campaign=campaign,
            user=user,
            membership=None,
            elevated=True,
        )
