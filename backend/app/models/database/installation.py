from datetime import datetime, timezone

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Installation(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_installation_singleton"),
    )

    id: int = Field(default=1, primary_key=True)
    installation_id: str = Field(index=True, unique=True)
    mode: str
    initialized_at: datetime = Field(default_factory=utc_now)
