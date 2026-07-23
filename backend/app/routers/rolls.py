from fastapi import APIRouter, Depends

from app.dependencies.campaigns import get_campaign_context
from app.models.api.rolls import (
    CampaignRollStats,
    RollCreate,
    RollCreateResponse,
    SessionRollStats,
)
from app.services.campaign_context import CampaignContext
from app.services.rolls import RollService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/rolls",
    tags=["rolls"],
)


@router.get("/campaign-stats")
def get_campaign_roll_stats(
    campaign_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> CampaignRollStats:
    return RollService(context).get_campaign_stats()


@router.get("/sessions/{session_id}")
def get_session_roll_stats(
    campaign_id: int,
    session_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> SessionRollStats:
    return RollService(context).get_session_stats(session_id)


@router.post("")
def create_roll(
    campaign_id: int,
    roll_create: RollCreate,
    context: CampaignContext = Depends(get_campaign_context),
) -> RollCreateResponse:
    return RollService(context).create(roll_create)


@router.delete("/sessions/{session_id}")
def delete_session_rolls(
    campaign_id: int,
    session_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> dict[str, bool]:
    RollService(context).delete_for_session(session_id)
    return {"deleted": True}
