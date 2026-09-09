from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.auth.enums import SecurityEventType, SystemRole, UserStatus
from app.auth.events import SecurityEventService
from app.auth.models import User
from app.authorization.capabilities import ROLE_CAPABILITIES
from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignCapability, CampaignRole
from app.authorization.models import CampaignMembership
from app.authorization.resource_policy import (
    has_personal_note_access,
    stage_release_personal_note_access,
)
from app.authorization.schemas import (
    CampaignMembershipRead,
    CampaignOwnershipTransferRead,
)
from app.models.database import CharacterProfile, Person


class CampaignMembershipService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db
        self.events = SecurityEventService(self.db)

    def to_read(
        self,
        membership: CampaignMembership,
        user: User,
    ) -> CampaignMembershipRead:
        return CampaignMembershipRead(
            id=membership.id,
            user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=membership.role,
            assigned_character_person_id=(
                membership.assigned_character_person_id
            ),
            active_character_person_id=(
                membership.active_character_person_id
            ),
            capabilities=sorted(
                ROLE_CAPABILITIES[membership.role],
                key=lambda capability: capability.value,
            ),
        )

    def list_reads(self) -> list[CampaignMembershipRead]:
        self.context.require(CampaignCapability.MEMBERSHIP_READ)
        rows = self.db.exec(
            select(CampaignMembership, User)
            .join(User, User.id == CampaignMembership.user_id)
            .where(
                CampaignMembership.campaign_id
                == self.context.campaign_id,
                CampaignMembership.is_custodial.is_(False),
                User.status != UserStatus.DELETED,
            )
            .order_by(func.lower(User.username), User.id)
        ).all()
        return [
            self.to_read(membership, user)
            for membership, user in rows
        ]

    def change_role(
        self,
        user_id: int,
        role: CampaignRole,
    ) -> CampaignMembershipRead:
        self.context.require(CampaignCapability.MEMBERSHIP_MANAGE)
        membership, user = self._get_human_member(user_id)
        if (
            membership.role is CampaignRole.OWNER
            and role is not CampaignRole.OWNER
        ):
            self._require_another_enabled_owner(user_id)
        membership.role = role
        self.db.add(membership)
        self._record_change(
            user_id,
            reason=f"action=role_changed role={role.value}",
        )
        self.db.commit()
        self.db.refresh(membership)
        return self.to_read(membership, user)

    def remove_user(self, user_id: int) -> None:
        self.context.require(CampaignCapability.MEMBERSHIP_MANAGE)
        membership, _ = self._get_human_member(user_id)
        if membership.role is CampaignRole.OWNER:
            self._require_another_enabled_owner(user_id)
        self._release_resource_access(user_id)
        self.db.delete(membership)
        self._record_change(
            user_id,
            reason="action=member_removed",
        )
        self.db.commit()

    def leave(self) -> None:
        membership = self.context.membership
        if membership.role is CampaignRole.OWNER:
            self._require_another_enabled_owner(self.context.user.id)
        self._release_resource_access(self.context.user.id)
        self.db.delete(membership)
        self._record_change(
            self.context.user.id,
            reason="action=member_left",
        )
        self.db.commit()

    def transfer_ownership(
        self,
        user_id: int,
    ) -> CampaignOwnershipTransferRead:
        self.context.require(CampaignCapability.MEMBERSHIP_MANAGE)
        current = self.context.membership
        if current.role is not CampaignRole.OWNER:
            raise HTTPException(
                status_code=403,
                detail="Campaign ownership is required",
            )
        if user_id == self.context.user.id:
            raise HTTPException(
                status_code=409,
                detail="Select another campaign member",
            )
        target, target_user = self._get_human_member(user_id)
        if (
            target_user.status is not UserStatus.ACTIVE
            or not target_user.can_login
        ):
            raise HTTPException(
                status_code=409,
                detail="Ownership requires an enabled campaign member",
            )

        current.role = CampaignRole.MEMBER
        target.role = CampaignRole.OWNER
        self.db.add(current)
        self.db.add(target)
        self._record_change(
            target_user.id,
            reason=(
                "action=ownership_transferred "
                f"previous_owner_user_id={self.context.user.id}"
            ),
        )
        self.db.commit()
        self.db.refresh(current)
        self.db.refresh(target)
        return CampaignOwnershipTransferRead(
            previous_owner=self.to_read(
                current,
                self.context.user,
            ),
            new_owner=self.to_read(target, target_user),
        )

    def assign_character(
        self,
        user_id: int,
        person_id: int | None,
    ) -> CampaignMembershipRead:
        self.context.require(CampaignCapability.CHARACTER_ASSIGN)
        membership, user = self._get_human_member(user_id)
        if person_id is not None:
            person = self.db.get(Person, person_id)
            profile = self.db.get(CharacterProfile, person_id)
            if (
                person is None
                or person.campaign_id != self.context.campaign_id
                or profile is None
            ):
                raise HTTPException(
                    status_code=404,
                    detail="Character profile not found",
                )
            assigned = self.db.exec(
                select(CampaignMembership).where(
                    CampaignMembership.campaign_id
                    == self.context.campaign_id,
                    CampaignMembership.assigned_character_person_id
                    == person_id,
                    CampaignMembership.user_id != user_id,
                )
            ).first()
            if assigned is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Character is assigned to another member",
                )
        membership.assigned_character_person_id = person_id
        if membership.active_character_person_id != person_id:
            membership.active_character_person_id = None
        self.db.add(membership)
        self._record_change(
            user_id,
            reason=(
                f"character_person_id={person_id}"
                if person_id is not None
                else "character_person_id=none"
            ),
        )
        self.db.commit()
        self.db.refresh(membership)
        return self.to_read(membership, user)

    def _get_human_member(
        self,
        user_id: int,
    ) -> tuple[CampaignMembership, User]:
        row = self.db.exec(
            select(CampaignMembership, User)
            .join(User, User.id == CampaignMembership.user_id)
            .where(
                CampaignMembership.campaign_id
                == self.context.campaign_id,
                CampaignMembership.user_id == user_id,
                CampaignMembership.is_custodial.is_(False),
            )
        ).first()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Campaign member not found",
            )
        return row

    def _require_another_enabled_owner(
        self,
        excluded_user_id: int,
    ) -> None:
        another_owner = self.db.exec(
            select(CampaignMembership.id)
            .join(User, User.id == CampaignMembership.user_id)
            .where(
                CampaignMembership.campaign_id
                == self.context.campaign_id,
                CampaignMembership.role == CampaignRole.OWNER,
                CampaignMembership.is_custodial.is_(False),
                CampaignMembership.user_id != excluded_user_id,
                User.status == UserStatus.ACTIVE,
                User.can_login.is_(True),
            )
            .limit(1)
        ).first()
        if another_owner is None:
            raise HTTPException(
                status_code=409,
                detail="Campaign must retain an enabled human owner",
            )

    def _record_change(
        self,
        user_id: int,
        *,
        reason: str | None = None,
    ) -> None:
        self.events.record(
            SecurityEventType.MEMBERSHIP_CHANGED,
            user_id=user_id,
            actor_user_id=self.context.user.id,
            campaign_id=self.context.campaign_id,
            reason=reason,
        )

    def _release_resource_access(self, user_id: int) -> None:
        if not has_personal_note_access(
            self.db,
            campaign_id=self.context.campaign_id,
            user_id=user_id,
        ):
            return
        custodian_id = self.db.exec(
            select(User.id).where(
                User.system_role == SystemRole.CUSTODIAN,
                User.status == UserStatus.ACTIVE,
                User.can_login.is_(False),
            )
        ).first()
        if custodian_id is None:
            raise HTTPException(
                status_code=409,
                detail="Resource custody cannot be assigned safely",
            )
        stage_release_personal_note_access(
            self.db,
            campaign_id=self.context.campaign_id,
            user_id=user_id,
            replacement_owner_user_id=custodian_id,
        )
