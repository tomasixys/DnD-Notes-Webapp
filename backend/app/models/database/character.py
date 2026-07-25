from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from app.authorization.enums import ResourceVisibility

from .note import NoteBase

if TYPE_CHECKING:
    from .person import Person
    from .inventory import InventoryAccess


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resource_visibility_enum() -> SAEnum:
    return SAEnum(
        ResourceVisibility,
        values_callable=lambda enum: [member.value for member in enum],
        native_enum=False,
        create_constraint=True,
        name="resource_visibility",
    )


class PersonalNoteAccess:
    created_by_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )
    visibility: ResourceVisibility = Field(
        default=ResourceVisibility.CAMPAIGN,
        sa_type=resource_visibility_enum(),
        index=True,
    )
    access_owner_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="RESTRICT",
        index=True,
    )


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
    inventory_access: list["InventoryAccess"] = Relationship(
        back_populates="character_profile",
        cascade_delete=True,
        passive_deletes=True,
    )


class CharacterNote(NoteBase, PersonalNoteAccess, table=True):
    __table_args__ = (
        CheckConstraint(
            "visibility = 'campaign' "
            "OR access_owner_user_id IS NOT NULL",
            name="ck_character_note_private_owner",
        ),
    )
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


class BackstoryNote(NoteBase, PersonalNoteAccess, table=True):
    __table_args__ = (
        CheckConstraint(
            "visibility = 'campaign' "
            "OR access_owner_user_id IS NOT NULL",
            name="ck_backstory_note_private_owner",
        ),
    )
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
