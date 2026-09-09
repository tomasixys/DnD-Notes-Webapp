from datetime import datetime, timezone

from sqlmodel import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RevisionField:
    revision: int = Field(default=1, ge=1, index=True)


class MutableAggregate(RevisionField):
    updated_at: datetime = Field(default_factory=utc_now)
