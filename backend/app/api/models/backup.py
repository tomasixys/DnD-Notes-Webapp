from sqlmodel import Field, SQLModel

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


class CampaignBackupCoinEntry(SQLModel):
    value: int
    type: str


class CampaignBackupLootItem(SQLModel):
    name: str
    desc: str = ""
    value: CampaignBackupCoinEntry


class CampaignBackupPartyStash(SQLModel):
    coins: list[CampaignBackupCoinEntry] = Field(default_factory=list)
    loot: list[CampaignBackupLootItem] = Field(default_factory=list)


class CampaignBackup(SQLModel):
    schema_version: int = CAMPAIGN_BACKUP_SCHEMA_VERSION
    campaign: CampaignBackupCampaign
    sessions: list[CampaignBackupSession] = Field(default_factory=list)
    people: list[CampaignBackupPerson] = Field(default_factory=list)
    locations: list[CampaignBackupLocation] = Field(default_factory=list)
    factions: list[CampaignBackupFaction] = Field(default_factory=list)
    party_stash: CampaignBackupPartyStash | None = None


