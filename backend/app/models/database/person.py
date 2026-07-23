from typing import TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .campaign import Campaign
    from .character import CharacterProfile


class Person(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    campaign: "Campaign" = Relationship(back_populates="people")
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
    )

    name: str
    role: str = ""
    description: str = ""

    character_profile: "CharacterProfile" = Relationship(
        back_populates="person",
        cascade_delete=True,
        passive_deletes=True,
        sa_relationship_kwargs={"uselist": False},
    )
