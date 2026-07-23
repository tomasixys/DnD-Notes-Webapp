from sqlmodel import SQLModel


class RollCreate(SQLModel):
    session_id: int
    roll: int


class SessionRollStats(SQLModel):
    campaign_id: int
    session_id: int
    rolls: list[int]
    average: float
    roll_luck: float


class CampaignRollStats(SQLModel):
    campaign_id: int
    num_rolls: int
    roll_avg: float
    roll_luck: float


class RollMutationResponse(SQLModel):
    campaign_stats: CampaignRollStats
    session_stats: SessionRollStats
