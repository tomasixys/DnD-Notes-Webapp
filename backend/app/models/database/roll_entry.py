from typing import TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .session_note import SessionNote


class RollEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    session: "SessionNote" = Relationship(back_populates="rolls")
    session_id: int = Field(
        foreign_key="sessionnote.id",
        ondelete="CASCADE",
    )

    roll: int
