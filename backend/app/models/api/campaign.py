from sqlmodel import SQLModel


class CampaignRead(SQLModel):
    id: int
    name: str
    player_character: str = ""
    description: str = ""
    session_count: int = 0
    image_url: str = ""
    banner_image_url: str = ""
    active_character_person_id: int | None = None
