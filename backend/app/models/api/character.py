from datetime import datetime

from sqlmodel import Field, SQLModel

from app.authorization.enums import (
    ResourceGrantPermission,
    ResourceVisibility,
)

from .person import PersonData, PersonRead
from .tag import ResourceTagRead
from .revision import RevisionRead


class CharacterCreate(SQLModel):
    """Create a profile for either a new or an existing Person."""

    person_id: int | None = None
    person: PersonData | None = None
    short_bio: str = ""
    appearance: str = ""
    make_active: bool = True


class CharacterUpdate(SQLModel):
    person: PersonData
    short_bio: str = ""
    appearance: str = ""


class CharacterRead(RevisionRead):
    person: PersonRead
    short_bio: str = ""
    appearance: str = ""
    image_url: str = ""
    is_active: bool = False


class CharacterDeleteResponse(SQLModel):
    deleted_id: int
    active_character: CharacterRead | None = None


class CharacterNoteGrantData(SQLModel):
    user_id: int
    permission: ResourceGrantPermission = ResourceGrantPermission.READ


class CharacterNoteGrantRead(CharacterNoteGrantData):
    username: str
    display_name: str = ""


class CharacterNoteData(SQLModel):
    title: str
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    visibility: ResourceVisibility = ResourceVisibility.CAMPAIGN
    grants: list[CharacterNoteGrantData] = Field(default_factory=list)


class CharacterNoteRead(CharacterNoteData):
    id: int
    campaign_id: int
    character_person_id: int
    created_at: datetime
    updated_at: datetime
    revision: int
    created_by_user_id: int | None = None
    access_owner_user_id: int | None = None
    grants: list[CharacterNoteGrantRead] = Field(default_factory=list)
    can_write: bool = False
    can_manage_access: bool = False
    tags: list[ResourceTagRead] = Field(default_factory=list)


class BackstoryNoteRead(CharacterNoteRead):
    pass
