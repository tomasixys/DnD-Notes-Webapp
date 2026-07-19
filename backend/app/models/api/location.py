from sqlmodel import Field, SQLModel

from .tag import ResourceTagRead


class LocationData(SQLModel):
    name: str
    type: str = ""
    parent_location: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class LocationRead(LocationData):
    id: int
    campaign_id: int
    tags: list[ResourceTagRead] = Field(default_factory=list)
