from sqlmodel import Field, SQLModel

from .tag import ResourceTagRead


class LocationBase(SQLModel):
    name: str
    type: str = ""
    description: str = ""


class LocationData(LocationBase):
    parent_location: str = ""
    tags: list[str] = Field(default_factory=list)


class LocationRead(LocationBase):
    id: int
    campaign_id: int
    parent_location: ResourceTagRead | None = None
    people: list[ResourceTagRead] = Field(default_factory=list)
    tags: list[ResourceTagRead] = Field(default_factory=list)
