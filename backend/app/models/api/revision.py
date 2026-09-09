from datetime import datetime

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class RevisionRead(SQLModel):
    revision: int = Field(default=1, ge=1)
    updated_at: datetime = Field(default_factory=utc_now)
