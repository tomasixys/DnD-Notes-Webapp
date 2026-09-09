from datetime import datetime

from sqlmodel import Field, SQLModel


class CampaignChangeRead(SQLModel):
    sequence: int
    resource_type: str
    resource_id: int | None = None
    action: str
    revision: int | None = None
    created_at: datetime


class CampaignChangesRead(SQLModel):
    cursor: int = 0
    changes: list[CampaignChangeRead] = Field(default_factory=list)
