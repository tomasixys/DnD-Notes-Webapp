from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CampaignChange(SQLModel, table=True):
    __tablename__ = "campaign_change"

    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    user_id: int = Field(
        foreign_key="app_user.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    sequence: int = Field(primary_key=True, ge=1)
    resource_type: str = Field(index=True)
    resource_id: int | None = Field(default=None, index=True)
    action: str
    revision: int | None = None
    source_client_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
