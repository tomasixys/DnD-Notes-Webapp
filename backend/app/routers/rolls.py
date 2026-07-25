from fastapi import APIRouter, Depends

from app.authorization.dependencies import (
    get_shared_read_context,
    get_shared_write_context,
)
from app.models.api.rolls import (
    CampaignRollStats,
    EpisodeRollStats,
    RollCreate,
    RollMutationResponse,
)
from app.services.campaign_context import CampaignContext
from app.services.rolls import RollService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/rolls",
    tags=["rolls"],
)


@router.get("/campaign-stats")
def get_campaign_roll_stats(
    context: CampaignContext = Depends(get_shared_read_context),
) -> CampaignRollStats:
    return RollService(context).get_campaign_stats()


@router.get("/sessions/{episode_id}")
def get_episode_roll_stats(
    episode_id: int,
    context: CampaignContext = Depends(get_shared_read_context),
) -> EpisodeRollStats:
    return RollService(context).get_episode_stats(episode_id)


@router.post("")
def create_roll(
    roll_create: RollCreate,
    context: CampaignContext = Depends(get_shared_write_context),
) -> RollMutationResponse:
    return RollService(context).create(roll_create)


@router.delete("/sessions/{episode_id}")
def delete_episode_rolls(
    episode_id: int,
    context: CampaignContext = Depends(get_shared_write_context),
) -> RollMutationResponse:
    return RollService(context).delete_for_episode(episode_id)
