from fastapi import APIRouter, Depends

from app.dependencies.campaigns import get_campaign_context
from app.models.api import FactionData
from app.services.campaign_context import CampaignContext
from app.services.factions import FactionService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/factions",
    tags=["factions"],
)


@router.get("")
def get_factions_for_campaign(
    campaign_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    factions = FactionService(context)
    return [factions.to_read(faction) for faction in factions.list()]


@router.get("/{faction_id}")
def get_faction(
    campaign_id: int,
    faction_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    factions = FactionService(context)
    return factions.to_read(factions.get(faction_id))


@router.post("")
def create_faction(
    campaign_id: int,
    faction: FactionData,
    context: CampaignContext = Depends(get_campaign_context),
):
    return FactionService(context).create(faction)


@router.put("/{faction_id}")
def update_faction(
    campaign_id: int,
    faction_id: int,
    updated_faction: FactionData,
    context: CampaignContext = Depends(get_campaign_context),
):
    return FactionService(context).update(
        faction_id,
        updated_faction,
    )


@router.delete("/{faction_id}")
def delete_faction(
    campaign_id: int,
    faction_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    FactionService(context).delete(faction_id)
    return {"deleted": True}
