from typing import TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .session_note import SessionNote
    from .person import Person
    from .location import Location
    from .faction import Faction
    from .tag import Tag


class Campaign(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    player_character: str = ""
    description: str = ""
    image_path: str = ""
    banner_image_path: str = ""

    sessions: list["SessionNote"] = Relationship(
        back_populates="campaign",
        cascade_delete=True,
        passive_deletes=True,
    )

    people: list["Person"] = Relationship(
        back_populates="campaign",
        cascade_delete=True,
        passive_deletes=True,
    )

    locations: list["Location"] = Relationship(
        back_populates="campaign",
        cascade_delete=True,
        passive_deletes=True,
    )

    factions: list["Faction"] = Relationship(
        back_populates="campaign",
        cascade_delete=True,
        passive_deletes=True,
    )

    tag_definitions: list["Tag"] = Relationship(
        back_populates="campaign",
        cascade_delete=True,
        passive_deletes=True,
    )
