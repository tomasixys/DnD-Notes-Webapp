from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth.enums import SecurityEventType, SystemRole, UserStatus
from app.auth.events import SecurityEventService
from app.auth.models import User
from app.auth.passwords import normalize_username, utc_now
from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignCapability, CampaignRole
from app.authorization.memberships import CampaignMembershipService
from app.authorization.models import (
    CampaignInvitation,
    CampaignMembership,
)
from app.authorization.schemas import (
    CampaignInvitationAcceptanceRead,
    CampaignInvitationRead,
    CampaignInvitationStatus,
    IssuedCampaignInvitationRead,
)
from app.models.database import Campaign


CAMPAIGN_INVITATION_TOKEN_BYTES = 32
INVALID_CAMPAIGN_INVITATION = "Invalid or expired campaign invitation."


class CampaignInvitationError(RuntimeError):
    """Raised when a campaign invitation cannot be changed safely."""


def invitation_token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class CampaignInvitationService:
    def __init__(
        self,
        db: Session,
        actor: User,
        *,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[int], str] | None = None,
    ):
        self.db = db
        self.actor = actor
        self.clock = clock or utc_now
        self.token_factory = token_factory or secrets.token_urlsafe
        self.events = SecurityEventService(db, clock=self.clock)

    def list_for_campaign(
        self,
        context: CampaignContext,
    ) -> list[CampaignInvitationRead]:
        context.require(CampaignCapability.MEMBERSHIP_MANAGE)
        rows = self.db.exec(
            select(CampaignInvitation, User)
            .join(User, User.id == CampaignInvitation.invited_user_id)
            .where(
                CampaignInvitation.campaign_id == context.campaign_id
            )
            .order_by(CampaignInvitation.created_at.desc())
        ).all()
        return [
            self._to_read(invitation, user, context.campaign)
            for invitation, user in rows
        ]

    def list_pending(self) -> list[CampaignInvitationRead]:
        now = self.clock()
        rows = self.db.exec(
            select(CampaignInvitation, User, Campaign)
            .join(User, User.id == CampaignInvitation.invited_user_id)
            .join(Campaign, Campaign.id == CampaignInvitation.campaign_id)
            .where(
                CampaignInvitation.invited_user_id == self.actor.id,
                CampaignInvitation.accepted_at.is_(None),
                CampaignInvitation.revoked_at.is_(None),
                CampaignInvitation.expires_at > now,
                Campaign.orphaned.is_(False),
            )
            .order_by(CampaignInvitation.expires_at)
        ).all()
        return [
            self._to_read(invitation, user, campaign)
            for invitation, user, campaign in rows
        ]

    def issue(
        self,
        context: CampaignContext,
        username: str,
        role: CampaignRole,
        *,
        lifetime_minutes: int,
    ) -> IssuedCampaignInvitationRead:
        context.require(CampaignCapability.MEMBERSHIP_MANAGE)
        user = self._find_invitable_user(username)
        self._require_not_member(context.campaign_id, user.id)

        invitation = self.db.exec(
            select(CampaignInvitation)
            .where(
                CampaignInvitation.campaign_id == context.campaign_id,
                CampaignInvitation.invited_user_id == user.id,
            )
            .with_for_update()
        ).first()
        if (
            invitation is not None
            and self._status(invitation)
            is CampaignInvitationStatus.PENDING
        ):
            raise CampaignInvitationError(
                "That user already has a pending campaign invitation."
            )
        if invitation is None:
            invitation = CampaignInvitation(
                campaign_id=context.campaign_id,
                invited_user_id=user.id,
                role=role,
                token_digest="",
                created_by_user_id=self.actor.id,
                expires_at=self.clock(),
            )
        try:
            token = self._replace_token(
                invitation,
                role,
                lifetime_minutes=lifetime_minutes,
            )
            self.events.record(
                SecurityEventType.MEMBERSHIP_CHANGED,
                user_id=user.id,
                actor_user_id=self.actor.id,
                campaign_id=context.campaign_id,
                reason=f"action=invitation_created role={role.value}",
            )
            self._commit("The campaign invitation could not be created.")
        except IntegrityError as error:
            self.db.rollback()
            raise CampaignInvitationError(
                "The campaign invitation could not be created."
            ) from error
        self.db.refresh(invitation)
        return IssuedCampaignInvitationRead(
            invitation=self._to_read(
                invitation,
                user,
                context.campaign,
            ),
            token=token,
        )

    def replace(
        self,
        context: CampaignContext,
        invitation_id: int,
        *,
        lifetime_minutes: int,
    ) -> IssuedCampaignInvitationRead:
        context.require(CampaignCapability.MEMBERSHIP_MANAGE)
        invitation, user = self._get_campaign_invitation(
            context.campaign_id,
            invitation_id,
        )
        self._require_not_member(context.campaign_id, user.id)
        try:
            token = self._replace_token(
                invitation,
                invitation.role,
                lifetime_minutes=lifetime_minutes,
            )
            self.events.record(
                SecurityEventType.MEMBERSHIP_CHANGED,
                user_id=user.id,
                actor_user_id=self.actor.id,
                campaign_id=context.campaign_id,
                reason=(
                    "action=invitation_replaced "
                    f"role={invitation.role.value}"
                ),
            )
            self._commit("The campaign invitation could not be replaced.")
        except IntegrityError as error:
            self.db.rollback()
            raise CampaignInvitationError(
                "The campaign invitation could not be replaced."
            ) from error
        self.db.refresh(invitation)
        return IssuedCampaignInvitationRead(
            invitation=self._to_read(
                invitation,
                user,
                context.campaign,
            ),
            token=token,
        )

    def revoke(
        self,
        context: CampaignContext,
        invitation_id: int,
    ) -> CampaignInvitationRead:
        context.require(CampaignCapability.MEMBERSHIP_MANAGE)
        invitation, user = self._get_campaign_invitation(
            context.campaign_id,
            invitation_id,
        )
        if (
            invitation.accepted_at is not None
            or invitation.revoked_at is not None
        ):
            raise CampaignInvitationError(
                "Only a pending campaign invitation can be revoked."
            )
        invitation.revoked_at = self.clock()
        self.db.add(invitation)
        self.events.record(
            SecurityEventType.MEMBERSHIP_CHANGED,
            user_id=user.id,
            actor_user_id=self.actor.id,
            campaign_id=context.campaign_id,
            reason="action=invitation_revoked",
        )
        self.db.commit()
        self.db.refresh(invitation)
        return self._to_read(invitation, user, context.campaign)

    def accept(
        self,
        raw_token: str = "",
        *,
        invitation_id: int | None = None,
    ) -> CampaignInvitationAcceptanceRead:
        if not raw_token and invitation_id is None:
            raise CampaignInvitationError(INVALID_CAMPAIGN_INVITATION)
        selector = (
            CampaignInvitation.id == invitation_id
            if invitation_id is not None
            else CampaignInvitation.token_digest == invitation_token_digest(raw_token)
        )
        invitation = self.db.exec(
            select(CampaignInvitation)
            .where(
                selector,
                CampaignInvitation.invited_user_id == self.actor.id,
            )
            .with_for_update()
        ).first()
        now = self.clock()
        if (
            invitation is None
            or invitation.invited_user_id != self.actor.id
            or invitation.accepted_at is not None
            or invitation.revoked_at is not None
            or as_utc(invitation.expires_at) <= as_utc(now)
            or self.actor.status is not UserStatus.ACTIVE
            or not self.actor.can_login
            or self.actor.system_role is SystemRole.CUSTODIAN
        ):
            raise CampaignInvitationError(INVALID_CAMPAIGN_INVITATION)
        campaign = self.db.get(Campaign, invitation.campaign_id)
        if campaign is None or campaign.orphaned:
            raise CampaignInvitationError(INVALID_CAMPAIGN_INVITATION)
        if self._membership(
            invitation.campaign_id,
            self.actor.id,
        ) is not None:
            raise CampaignInvitationError(INVALID_CAMPAIGN_INVITATION)

        membership = CampaignMembership(
            campaign_id=invitation.campaign_id,
            user_id=self.actor.id,
            role=invitation.role,
        )
        invitation.accepted_at = now
        self.db.add(membership)
        self.db.add(invitation)
        try:
            self.db.flush()
            self.events.record(
                SecurityEventType.MEMBERSHIP_CHANGED,
                user_id=self.actor.id,
                actor_user_id=self.actor.id,
                campaign_id=invitation.campaign_id,
                reason=(
                    "action=invitation_accepted "
                    f"role={invitation.role.value}"
                ),
            )
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise CampaignInvitationError(
                INVALID_CAMPAIGN_INVITATION
            ) from error

        self.db.refresh(invitation)
        self.db.refresh(membership)
        context = CampaignContext(
            self.db,
            campaign,
            self.actor,
            membership,
        )
        return CampaignInvitationAcceptanceRead(
            invitation=self._to_read(
                invitation,
                self.actor,
                campaign,
            ),
            membership=CampaignMembershipService(
                context
            ).to_read(membership, self.actor),
        )

    def decline(self, invitation_id: int) -> CampaignInvitationRead:
        invitation = self.db.exec(select(CampaignInvitation).where(
            CampaignInvitation.id == invitation_id,
            CampaignInvitation.invited_user_id == self.actor.id,
        ).with_for_update()).first()
        if (
            invitation is None
            or self._status(invitation) is not CampaignInvitationStatus.PENDING
            or self.actor.status is not UserStatus.ACTIVE
            or not self.actor.can_login
        ):
            raise CampaignInvitationError(INVALID_CAMPAIGN_INVITATION)
        campaign = self.db.get(Campaign, invitation.campaign_id)
        if campaign is None or campaign.orphaned:
            raise CampaignInvitationError(INVALID_CAMPAIGN_INVITATION)
        invitation.revoked_at = self.clock()
        self.db.add(invitation)
        self.events.record(
            SecurityEventType.MEMBERSHIP_CHANGED,
            user_id=self.actor.id, actor_user_id=self.actor.id,
            campaign_id=campaign.id, reason="action=invitation_declined",
        )
        self.db.commit()
        self.db.refresh(invitation)
        return self._to_read(invitation, self.actor, campaign)

    def _replace_token(
        self,
        invitation: CampaignInvitation,
        role: CampaignRole,
        *,
        lifetime_minutes: int,
    ) -> str:
        now = self.clock()
        token = self.token_factory(CAMPAIGN_INVITATION_TOKEN_BYTES)
        invitation.role = role
        invitation.token_digest = invitation_token_digest(token)
        invitation.created_by_user_id = self.actor.id
        invitation.created_at = now
        invitation.expires_at = now + timedelta(
            minutes=lifetime_minutes
        )
        invitation.accepted_at = None
        invitation.revoked_at = None
        self.db.add(invitation)
        self.db.flush()
        return token

    def _get_campaign_invitation(
        self,
        campaign_id: int,
        invitation_id: int,
    ) -> tuple[CampaignInvitation, User]:
        row = self.db.exec(
            select(CampaignInvitation, User)
            .join(User, User.id == CampaignInvitation.invited_user_id)
            .where(
                CampaignInvitation.id == invitation_id,
                CampaignInvitation.campaign_id == campaign_id,
            )
            .with_for_update()
        ).first()
        if row is None:
            raise CampaignInvitationError(
                "Campaign invitation not found."
            )
        return row

    def _find_invitable_user(self, username: str) -> User:
        normalized = normalize_username(username)
        user = self.db.exec(
            select(User).where(
                User.normalized_username == normalized,
                User.status.in_(
                    (UserStatus.PENDING, UserStatus.ACTIVE)
                ),
                User.can_login.is_(True),
                User.system_role != SystemRole.CUSTODIAN,
            )
        ).first()
        if user is None:
            raise CampaignInvitationError(
                "No invitable account has that username."
            )
        return user

    def _require_not_member(
        self,
        campaign_id: int,
        user_id: int,
    ) -> None:
        if self._membership(campaign_id, user_id) is not None:
            raise CampaignInvitationError(
                "User is already a campaign member."
            )

    def _membership(
        self,
        campaign_id: int,
        user_id: int,
    ) -> CampaignMembership | None:
        return self.db.exec(
            select(CampaignMembership).where(
                CampaignMembership.campaign_id == campaign_id,
                CampaignMembership.user_id == user_id,
            )
        ).first()

    def _status(
        self,
        invitation: CampaignInvitation,
    ) -> CampaignInvitationStatus:
        if invitation.accepted_at is not None:
            return CampaignInvitationStatus.ACCEPTED
        if invitation.revoked_at is not None:
            return CampaignInvitationStatus.REVOKED
        if as_utc(invitation.expires_at) <= as_utc(self.clock()):
            return CampaignInvitationStatus.EXPIRED
        return CampaignInvitationStatus.PENDING

    def _to_read(
        self,
        invitation: CampaignInvitation,
        user: User,
        campaign: Campaign,
    ) -> CampaignInvitationRead:
        return CampaignInvitationRead(
            id=invitation.id,
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            invited_user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=invitation.role,
            status=self._status(invitation),
            created_at=invitation.created_at,
            expires_at=invitation.expires_at,
        )

    def _commit(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise CampaignInvitationError(message) from error
