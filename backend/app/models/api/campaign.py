from sqlmodel import SQLModel

from app.authorization.enums import CampaignCapability, CampaignRole
from .revision import RevisionRead


class CampaignRead(RevisionRead):
    id: int
    name: str
    player_character: str = ""
    description: str = ""
    session_count: int = 0
    image_url: str = ""
    banner_image_url: str = ""
    active_character_person_id: int | None = None
    assigned_character_person_id: int | None = None
    membership_role: CampaignRole
    capabilities: list[CampaignCapability]
