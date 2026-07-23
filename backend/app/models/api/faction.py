from sqlmodel import Field, SQLModel

from .tag import ResourceTagRead


class FactionBase(SQLModel):
    name: str
    type: str = ""
    description: str = ""


class FactionData(FactionBase):
    location: str = ""
    tags: list[str] = Field(default_factory=list)


class FactionRead(FactionBase):
    id: int
    campaign_id: int
    location: ResourceTagRead | None = None
    members: list[ResourceTagRead] = Field(default_factory=list)
    tags: list[ResourceTagRead] = Field(default_factory=list)
