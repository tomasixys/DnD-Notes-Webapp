from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel, Relationship

###############################################################
#############  Database table Models  #########################
###############################################################

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

class SessionNote(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    campaign: "Campaign" = Relationship(back_populates="sessions")
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
    )

    date: str
    title: str
    description: str = ""
    session_number: int = Field(index=True)

    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )

    rolls: list["RollEntry"] = Relationship(
        back_populates="session",
        cascade_delete=True,
        passive_deletes=True,
)


class Person(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    campaign: "Campaign" = Relationship(back_populates="people")
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
    )

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
    id: int | None = Field(default=None, primary_key=True)

    campaign: "Campaign" = Relationship(back_populates="locations")
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
    )

    name: str
    type: str = ""
    parent_location: str = ""
    description: str = ""

    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )


class Faction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    
    campaign: "Campaign" = Relationship(back_populates="factions")
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
    )

    name: str
    type: str = ""
    location: str = ""
    description: str = ""

    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )


class RollEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    session: "SessionNote" = Relationship(back_populates="rolls")
    session_id: int = Field(
        foreign_key="sessionnote.id",
        ondelete="CASCADE",
    )

    roll: int


###############################################################
############# Backup Models for Export/Import #################
###############################################################
# Backup/export models
# These are not database tables. They describe the JSON backup format.

CAMPAIGN_BACKUP_SCHEMA_VERSION = 1
    
class CampaignBackupCampaign(SQLModel):
    name: str
    player_character: str = ""
    description: str = ""
    image_archive_path: str = ""
    banner_archive_path: str = ""


class CampaignBackupSession(SQLModel):
    date: str
    title: str
    description: str = ""
    session_number: int
    tags: list[str] = Field(default_factory=list)
    rolls: list[int] = Field(default_factory=list)


class CampaignBackupPerson(SQLModel):
    name: str
    role: str = ""
    faction: str = ""
    location: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class CampaignBackupLocation(SQLModel):
    name: str
    type: str = ""
    parent_location: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class CampaignBackupFaction(SQLModel):
    name: str
    type: str = ""
    location: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class CampaignBackup(SQLModel):
    schema_version: int = CAMPAIGN_BACKUP_SCHEMA_VERSION
    campaign: CampaignBackupCampaign
    sessions: list[CampaignBackupSession] = Field(default_factory=list)
    people: list[CampaignBackupPerson] = Field(default_factory=list)
    locations: list[CampaignBackupLocation] = Field(default_factory=list)
    factions: list[CampaignBackupFaction] = Field(default_factory=list)