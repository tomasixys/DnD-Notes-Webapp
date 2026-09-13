from sqlmodel import SQLModel


class AccountNotificationSummaryRead(SQLModel):
    pending_campaign_invitations: int = 0
    pending_issue_reports: int = 0
