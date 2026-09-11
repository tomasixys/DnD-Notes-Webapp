from sqlmodel import SQLModel


class RollCreate(SQLModel):
    session_id: int
    roll: int


class RollContributorStats(SQLModel):
    user_id: int | None
    display_name: str
    num_rolls: int
    average: float
    roll_luck: float


class EpisodeRollStats(SQLModel):
    campaign_id: int
    session_id: int
    user_id: int
    rolls: list[int]
    average: float
    roll_luck: float
    revision: int
    other_contributors: list[RollContributorStats]


class CampaignRollStats(SQLModel):
    campaign_id: int
    num_rolls: int
    roll_avg: float
    roll_luck: float


class RollMutationResponse(SQLModel):
    campaign_stats: CampaignRollStats
    session_stats: EpisodeRollStats
