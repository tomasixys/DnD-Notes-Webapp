from typing import TYPE_CHECKING
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel, Relationship

from app.api.models.enums import TagResolutionState

if TYPE_CHECKING:
    from .campaign import Campaign


class Tag(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("campaign_id", "key", name="uq_tag_campaign_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        index=True,
    )
    label: str
    normalized_label: str = Field(index=True)
    key: str
    reference_type: str | None = Field(default=None, index=True)
    reference_id: int | None = Field(default=None, index=True)
    resolution_state: str = Field(default=TagResolutionState.PASSIVE.value)

    campaign: "Campaign" = Relationship(back_populates="tag_definitions")
    assignments: list["TagAssignment"] = Relationship(
        back_populates="tag",
        cascade_delete=True,
        passive_deletes=True,
    )


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
