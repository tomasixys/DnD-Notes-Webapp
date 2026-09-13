from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.models.enums import IssueStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IssueReport(SQLModel, table=True):
    __tablename__ = "issue_report"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=160)
    description: str = Field(max_length=5000)
    status: IssueStatus = Field(
        default=IssueStatus.PENDING,
        sa_type=SAEnum(
            IssueStatus,
            values_callable=lambda enum: [member.value for member in enum],
            native_enum=False,
            create_constraint=True,
            name="issue_status",
        ),
        index=True,
    )
    reporter_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )
    reviewed_by_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )
    review_note: str = Field(default="", max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    reviewed_at: datetime | None = None
