from sqlmodel import Field, SQLModel

from .tag import ResourceTagRead


class SessionNoteData(SQLModel):
    date: str
    title: str
    description: str = ""
    session_number: int
    tags: list[str] = Field(default_factory=list)


class SessionNoteRead(SessionNoteData):
    id: int
    campaign_id: int
    tags: list[ResourceTagRead] = Field(default_factory=list)
