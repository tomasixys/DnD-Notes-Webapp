from sqlmodel import Field, SQLModel

from .tag import ResourceTagRead


class PersonData(SQLModel):
    name: str
    role: str = ""
    faction: str = ""
    location: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class PersonRead(PersonData):
    id: int
    campaign_id: int
    tags: list[ResourceTagRead] = Field(default_factory=list)
