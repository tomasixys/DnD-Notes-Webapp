from sqlmodel import SQLModel

from app.authorization.enums import CampaignCapability, CampaignRole


class CampaignMembershipRead(SQLModel):
    id: int
    user_id: int
    username: str
    display_name: str
    role: CampaignRole
    assigned_character_person_id: int | None = None
    active_character_person_id: int | None = None
    capabilities: list[CampaignCapability]


class CampaignMemberAdd(SQLModel):
    username: str
    role: CampaignRole = CampaignRole.MEMBER


class CampaignMemberRoleUpdate(SQLModel):
    role: CampaignRole


class CharacterAssignmentUpdate(SQLModel):
    character_person_id: int | None = None


class AdminCampaignRead(SQLModel):
    id: int
    name: str
    orphaned: bool


class CampaignRecoveryRequest(SQLModel):
    owner_user_id: int
    reason: str
