from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from .note import NoteBase

if TYPE_CHECKING:
    from .person import Person


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CharacterProfile(SQLModel, table=True):
    """Private character details extending a campaign Person record."""

    person_id: int = Field(
        primary_key=True,
        foreign_key="person.id",
        ondelete="CASCADE",
    )
    short_bio: str = ""
    appearance: str = ""
    image_path: str = ""

    person: "Person" = Relationship(back_populates="character_profile")
    notes: list["CharacterNote"] = Relationship(
        back_populates="character_profile",
        cascade_delete=True,
        passive_deletes=True,
    )
    backstory_notes: list["BackstoryNote"] = Relationship(
        back_populates="character_profile",
        cascade_delete=True,
        passive_deletes=True,
    )


class CharacterNote(NoteBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        index=True,
    )
    character_person_id: int = Field(
        foreign_key="characterprofile.person_id",
        ondelete="CASCADE",
        index=True,
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    character_profile: CharacterProfile = Relationship(back_populates="notes")


class BackstoryNote(NoteBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        index=True,
    )
    character_person_id: int = Field(
        foreign_key="characterprofile.person_id",
        ondelete="CASCADE",
        index=True,
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    character_profile: CharacterProfile = Relationship(
        back_populates="backstory_notes"
    )
