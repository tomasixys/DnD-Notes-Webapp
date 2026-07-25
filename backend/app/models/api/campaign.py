from sqlmodel import SQLModel


class ActiveCharacterRef(SQLModel):
    id: int
    name: str


class CampaignRead(SQLModel):
    id: int
    name: str
    description: str = ""
    session_count: int = 0
    image_url: str = ""
    banner_image_url: str = ""
    active_character: ActiveCharacterRef | None = None

