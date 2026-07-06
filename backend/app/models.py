from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Campaign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    player_character: str = ""
    description: str = ""
    
    image_path: str = ""
    banner_image_path: str = ""


class SessionNote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(index=True)

    session_number: int = Field(index=True)

    date: str
    title: str
    description: str = ""

    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )


class Person(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(index=True)

    name: str
    role: str = ""
    faction: str = ""
    location: str = ""
    description: str = ""

    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )


class Location(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(index=True)

    name: str
    type: str = ""
    parent_location: str = ""
    description: str = ""

    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )


class Faction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(index=True)

    name: str
    type: str = ""
    location: str = ""
    description: str = ""

    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )


class RollEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    campaign_id: int = Field(index=True)
    session_id: int = Field(index=True)

    roll: int



#################################
## Schemas for roll statistics ##
#################################
    
# class SessionRollStats(SQLModel):
#     campaign_id: int
#     session_id: int
#     rolls: list[int]
#     average: float
#     roll_luck: float


# class CampaignRollStats(SQLModel):
#     campaign_id: int
#     num_rolls: int
#     roll_avg: float
#     roll_luck: float