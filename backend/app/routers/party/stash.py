from fastapi import APIRouter, Depends

from app.models.api import PartyStashRead, PartyStashUpdate, LootItemRead, LootItemUpdate
from app.services.stash_service import StashService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/party/stash",
    tags=["party_stash"],
)


@router.get("", response_model=PartyStashRead)
def get_party_stash(
    campaign_id: int,
    service: StashService = Depends(),
):
    return service.get_stash(campaign_id)


@router.put("", response_model=PartyStashRead)
def update_party_stash(
    campaign_id: int,
    payload: PartyStashUpdate,
    service: StashService = Depends(),
):
    return service.update_stash(campaign_id, payload)


@router.put("/loot", response_model=LootItemRead)
def add_loot_item(
    campaign_id: int,
    payload: LootItemUpdate,
    service: StashService = Depends(),
):
    return service.add_loot_item(campaign_id, payload)


@router.delete("/loot/{loot_id}")
def delete_loot_item(
    campaign_id: int,
    loot_id: int,
    service: StashService = Depends(),
):
    return service.delete_loot_item(campaign_id, loot_id)
