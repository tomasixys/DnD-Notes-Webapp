from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import update
from sqlmodel import select

from app.auth.enums import UserStatus
from app.auth.models import User
from app.authorization.context import CampaignContext
from app.authorization.models import CampaignMembership
from app.models.api import CampaignChangeRead, CampaignChangesRead
from app.models.database import CampaignChange


class CampaignChangeService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    def stage_record(
        self,
        resource_type: str,
        resource_id: int | None,
        *,
        action: str,
        revision: int | None,
        recipient_user_ids: Iterable[int] | None = None,
    ) -> None:
        recipients = set(
            recipient_user_ids
            if recipient_user_ids is not None
            else self.db.exec(
                select(CampaignMembership.user_id)
                .join(User, User.id == CampaignMembership.user_id)
                .where(
                    CampaignMembership.campaign_id
                    == self.context.campaign_id,
                    CampaignMembership.is_custodial.is_(False),
                    User.status == UserStatus.ACTIVE,
                    User.can_login.is_(True),
                )
            ).all()
        )
        if not recipients:
            return

        valid_recipients = self.db.exec(
            select(CampaignMembership.user_id)
            .join(User, User.id == CampaignMembership.user_id)
            .where(
                CampaignMembership.campaign_id
                == self.context.campaign_id,
                CampaignMembership.user_id.in_(recipients),
                CampaignMembership.is_custodial.is_(False),
                User.status == UserStatus.ACTIVE,
                User.can_login.is_(True),
            )
        ).all()
        for user_id in valid_recipients:
            sequence = self.db.execute(
                update(CampaignMembership)
                .where(
                    CampaignMembership.campaign_id
                    == self.context.campaign_id,
                    CampaignMembership.user_id == user_id,
                )
                .values(
                    change_cursor=CampaignMembership.change_cursor + 1
                )
                .returning(CampaignMembership.change_cursor)
                .execution_options(synchronize_session=False)
            ).scalar_one()
            if (
                self.context.membership is not None
                and self.context.membership.user_id == user_id
            ):
                self.context.membership.change_cursor = sequence
            self.db.add(
                CampaignChange(
                    campaign_id=self.context.campaign_id,
                    user_id=user_id,
                    sequence=sequence,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    revision=revision,
                    source_client_id=self.context.client_instance_id,
                )
            )
        self.db.flush()

    def list_changes(
        self,
        after: int | None,
        *,
        limit: int = 100,
    ) -> CampaignChangesRead:
        membership = self.context.membership
        if membership is None:
            return CampaignChangesRead(cursor=0)
        if after is None:
            return CampaignChangesRead(cursor=membership.change_cursor)

        changes = self.db.exec(
            select(CampaignChange)
            .where(
                CampaignChange.campaign_id == self.context.campaign_id,
                CampaignChange.user_id == self.context.user.id,
                CampaignChange.sequence > after,
            )
            .order_by(CampaignChange.sequence)
            .limit(limit)
        ).all()
        cursor = changes[-1].sequence if changes else after
        visible_changes = [
            change
            for change in changes
            if (
                self.context.client_instance_id is None
                or change.source_client_id
                != self.context.client_instance_id
            )
        ]
        return CampaignChangesRead(
            cursor=cursor,
            changes=[
                CampaignChangeRead(
                    sequence=change.sequence,
                    resource_type=change.resource_type,
                    resource_id=change.resource_id,
                    action=change.action,
                    revision=change.revision,
                    created_at=change.created_at,
                )
                for change in visible_changes
            ],
        )
