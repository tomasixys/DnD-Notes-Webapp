from sqlmodel import Field, SQLModel

from .tag import ResourceTagRead


class PersonBase(SQLModel):
    name: str
    role: str = ""
    description: str = ""


class PersonData(PersonBase):
    faction: str = ""
    location: str = ""
    tags: list[str] = Field(default_factory=list)


class PersonRead(PersonBase):
    id: int
    campaign_id: int
    faction: ResourceTagRead | None = None
    location: ResourceTagRead | None = None
    tags: list[ResourceTagRead] = Field(default_factory=list)
    character_profile_available: bool = False
    is_active_character: bool = False
