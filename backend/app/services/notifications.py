from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.enums import SystemRole
from app.auth.models import User
from app.authorization.models import CampaignInvitation
from app.models.api import AccountNotificationSummaryRead
from app.models.database import Campaign, IssueReport
from app.models.enums import IssueStatus


class AccountNotificationService:
    def __init__(
        self,
        db: Session,
        user: User,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.user = user
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def summary(self) -> AccountNotificationSummaryRead:
        pending_invitations = int(
            self.db.exec(
                select(func.count(CampaignInvitation.id))
                .join(Campaign, Campaign.id == CampaignInvitation.campaign_id)
                .where(
                    CampaignInvitation.invited_user_id == self.user.id,
                    CampaignInvitation.accepted_at.is_(None),
                    CampaignInvitation.revoked_at.is_(None),
                    CampaignInvitation.expires_at > self.clock(),
                    Campaign.orphaned.is_(False),
                )
            ).one()
        )
        pending_issues = 0
        if self.user.system_role is SystemRole.ADMIN:
            pending_issues = int(
                self.db.exec(
                    select(func.count(IssueReport.id)).where(
                        IssueReport.status == IssueStatus.PENDING
                    )
                ).one()
            )
        return AccountNotificationSummaryRead(
            pending_campaign_invitations=pending_invitations,
            pending_issue_reports=pending_issues,
        )
