from sqlmodel import Field, SQLModel

from .tag import ResourceTagRead


class FactionData(SQLModel):
    name: str
    type: str = ""
    location: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class FactionRead(FactionData):
    id: int
    campaign_id: int
    tags: list[ResourceTagRead] = Field(default_factory=list)
