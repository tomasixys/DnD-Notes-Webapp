from datetime import datetime
from enum import Enum

from pydantic import SecretStr
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


class CampaignInvitationCreate(SQLModel):
    username: str
    role: CampaignRole = CampaignRole.MEMBER


class CampaignInvitationAccept(SQLModel):
    token: SecretStr


class CampaignInvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CampaignInvitationRead(SQLModel):
    id: int
    campaign_id: int
    campaign_name: str
    invited_user_id: int
    username: str
    display_name: str
    role: CampaignRole
    status: CampaignInvitationStatus
    created_at: datetime
    expires_at: datetime


class IssuedCampaignInvitationRead(SQLModel):
    invitation: CampaignInvitationRead
    token: str


class CampaignInvitationAcceptanceRead(SQLModel):
    invitation: CampaignInvitationRead
    membership: CampaignMembershipRead


class CampaignMemberRoleUpdate(SQLModel):
    role: CampaignRole


class CharacterAssignmentUpdate(SQLModel):
    character_person_id: int | None = None


class CampaignOwnershipTransferRead(SQLModel):
    previous_owner: CampaignMembershipRead
    new_owner: CampaignMembershipRead


class AdminCampaignRead(SQLModel):
    id: int
    name: str
    orphaned: bool


class CampaignRecoveryRequest(SQLModel):
    owner_user_id: int
    reason: str
