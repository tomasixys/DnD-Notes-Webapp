from typing import TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

from .note import NoteBase

if TYPE_CHECKING:
    from .campaign import Campaign
    from .roll_entry import RollEntry


class SessionNote(NoteBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    campaign: "Campaign" = Relationship(back_populates="sessions")
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
    )

    date: str
    session_number: int = Field(index=True)

    rolls: list["RollEntry"] = Relationship(
        back_populates="session",
        cascade_delete=True,
        passive_deletes=True,
    )
