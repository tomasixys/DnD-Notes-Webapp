from typing import TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .campaign import Campaign


class SessionNote(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    campaign: "Campaign" = Relationship(back_populates="sessions")
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
    )

    date: str
    title: str
    description: str = ""
    session_number: int = Field(index=True)

    rolls: list["RollEntry"] = Relationship(
        back_populates="session",
        cascade_delete=True,
        passive_deletes=True,
    )


class RollEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    session: "SessionNote" = Relationship(back_populates="rolls")
    session_id: int = Field(
        foreign_key="sessionnote.id",
        ondelete="CASCADE",
    )

    roll: int
