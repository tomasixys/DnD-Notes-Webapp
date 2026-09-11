from typing import TYPE_CHECKING

from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .episode import Episode


class RollEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    episode: "Episode" = Relationship(back_populates="rolls")
    session_id: int = Field(
        foreign_key="sessionnote.id",
        ondelete="CASCADE",
    )
    user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )

    roll: int
