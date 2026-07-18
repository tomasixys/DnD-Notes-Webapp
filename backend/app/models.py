from enum import Enum
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel, Relationship


class ResourceType(str, Enum):
    SESSION = "session"
    PERSON = "person"
    LOCATION = "location"
    FACTION = "faction"


class TagResolutionState(str, Enum):
    PASSIVE = "passive"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


###############################################################
#############  Database table Models  #########################
###############################################################
# These are database tables. They describe the database schema and are used to create the database tables.

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


class Tag(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("campaign_id", "key", name="uq_tag_campaign_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        index=True,
    )
    label: str
    normalized_label: str = Field(index=True)
    key: str
    reference_type: str | None = Field(default=None, index=True)
    reference_id: int | None = Field(default=None, index=True)
    resolution_state: str = Field(default=TagResolutionState.PASSIVE.value)

    campaign: "Campaign" = Relationship(back_populates="tag_definitions")
    assignments: list["TagAssignment"] = Relationship(
        back_populates="tag",
        cascade_delete=True,
        passive_deletes=True,
    )


class TagAssignment(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "tag_id",
            "owner_type",
            "owner_id",
            name="uq_tag_assignment_owner",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tag_id: int = Field(
        foreign_key="tag.id",
        ondelete="CASCADE",
        index=True,
    )
    owner_type: str = Field(index=True)
    owner_id: int = Field(index=True)

    tag: "Tag" = Relationship(back_populates="assignments")

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

class RollEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    session: "SessionNote" = Relationship(back_populates="rolls")
    session_id: int = Field(
        foreign_key="sessionnote.id",
        ondelete="CASCADE",
    )

    roll: int


###############################################################
############### Resource API Models ###########################
###############################################################

class ResourceTagRead(SQLModel):
    value: str
    label: str
    reference_type: ResourceType | None = None
    reference_id: int | None = None
    resolution_state: TagResolutionState


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

###############################################################
###############################################################


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

###############################################################
###############################################################



###############################################################
###############  Search Models  ###############################
###############################################################
# These are not database tables. They describe the search request and response format.
class SearchResourceType(str, Enum):
    SESSION = "session"
    PERSON = "person"
    LOCATION = "location"
    FACTION = "faction"

class SearchQueryDto(SQLModel):
    query: str
    resource_types: list[str] = Field(default_factory=list)

class SearchResultDto(SQLModel):
    campaign_id: int
    resource_type: str
    resource_id: int
    title: str
    context: str
    snippet: str
    matched_fields: list[str] = Field(default_factory=list)
    relevance: float

class SearchResponseDto(SQLModel):
    query: str
    searched_resource_types: list[str] = Field(default_factory=list)
    total_count: int
    results: list[SearchResultDto] = Field(default_factory=list)

###############################################################
###############################################################
