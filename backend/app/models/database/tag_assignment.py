from typing import TYPE_CHECKING
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .tag import Tag


class TagAssignment(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "tag_id",
            "owner_type",
            "owner_id",
            name="uq_tag_assignment_owner",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tag_id: int = Field(
        foreign_key="tag.id",
        ondelete="CASCADE",
        index=True,
    )
    owner_type: str = Field(index=True)
    owner_id: int = Field(index=True)

    tag: "Tag" = Relationship(back_populates="assignments")
