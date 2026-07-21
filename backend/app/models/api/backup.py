from datetime import datetime

from sqlmodel import Field, SQLModel

CAMPAIGN_BACKUP_SCHEMA_VERSION = 2


class CampaignBackupCampaign(SQLModel):
    name: str
    player_character: str = ""
    description: str = ""
    image_archive_path: str = ""
    banner_archive_path: str = ""
    active_character_person_backup_id: int | None = None


class CampaignBackupSession(SQLModel):
    date: str
    title: str
    description: str = ""
    session_number: int
    tags: list[str] = Field(default_factory=list)
    rolls: list[int] = Field(default_factory=list)


class CampaignBackupPerson(SQLModel):
    backup_id: int | None = None
    name: str
    role: str = ""
    faction: str = ""
    location: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class CampaignBackupCharacterNote(SQLModel):
    title: str
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CampaignBackupLegacyCharacterEntry(CampaignBackupCharacterNote):
    entry_type: str


class CampaignBackupCharacter(SQLModel):
    person_backup_id: int
    short_bio: str = ""
    appearance: str = ""
    image_archive_path: str = ""
    notes: list[CampaignBackupCharacterNote] = Field(default_factory=list)
    backstory_notes: list[CampaignBackupCharacterNote] = Field(default_factory=list)
    entries: list[CampaignBackupLegacyCharacterEntry] = Field(
        default_factory=list
    )


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
    characters: list[CampaignBackupCharacter] = Field(default_factory=list)
