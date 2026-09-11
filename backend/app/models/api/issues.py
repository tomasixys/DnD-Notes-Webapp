from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.enums import IssueStatus


class IssueReportCreate(SQLModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=5000)


class IssueModerationUpdate(SQLModel):
    status: IssueStatus
    review_note: str = Field(default="", max_length=1000)


class KnownIssueRead(SQLModel):
    id: int
    title: str
    description: str
    created_at: datetime
    acknowledged_at: datetime


class UserIssueRead(SQLModel):
    id: int
    title: str
    description: str
    status: IssueStatus
    review_note: str
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None


class AdminIssueRead(UserIssueRead):
    reporter_username: str
    reporter_display_name: str
