from fastapi import APIRouter, Depends

from app.authorization.dependencies import (
    get_shared_read_context,
    get_shared_write_context,
)
from app.models.api import DeleteResponse, EpisodeData, EpisodeRead
from app.services.campaign_context import CampaignContext
from app.services.episodes import EpisodeService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/sessions",
    tags=["episodes"],
)


@router.get("")
def get_episodes_for_campaign(
    context: CampaignContext = Depends(get_shared_read_context),
) -> list[EpisodeRead]:
    return EpisodeService(context).list_for_campaign()


@router.get("/{episode_id}")
def get_episode(
    episode_id: int,
    context: CampaignContext = Depends(get_shared_read_context),
) -> EpisodeRead:
    service = EpisodeService(context)
    return service.to_read(service.get(episode_id))


@router.post("")
def create_episode(
    episode: EpisodeData,
    context: CampaignContext = Depends(get_shared_write_context),
) -> EpisodeRead:
    return EpisodeService(context).create(episode)


@router.put("/{episode_id}")
def update_episode(
    episode_id: int,
    updated_episode: EpisodeData,
    context: CampaignContext = Depends(get_shared_write_context),
) -> EpisodeRead:
    return EpisodeService(context).update(
        episode_id, updated_episode
    )


@router.delete("/{episode_id}")
def delete_episode(
    episode_id: int,
    context: CampaignContext = Depends(get_shared_write_context),
) -> DeleteResponse:
    return EpisodeService(context).delete(episode_id)
