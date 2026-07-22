from sqlmodel import SQLModel


class NoteBase(SQLModel):
    """Fields shared by every persisted note type."""

    title: str
    content: str = ""
