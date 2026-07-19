from fastapi import APIRouter, Depends, Response

from app.models.api import (
    PartyStashCreate,
    PartyStashRead,
    PartyStashUpdate,
    LootItemRead,
    LootItemUpdate,
)
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


@router.post("", response_model=PartyStashRead, status_code=201)
def create_party_stash(
    campaign_id: int,
    payload: PartyStashCreate,
    service: StashService = Depends(),
):
    return service.create_stash(campaign_id, payload)


@router.put("", response_model=PartyStashRead)
def update_party_stash(
    campaign_id: int,
    payload: PartyStashUpdate,
    service: StashService = Depends(),
):
    return service.update_stash(campaign_id, payload)


@router.post("/loot", response_model=LootItemRead, status_code=201)
def add_loot_item(
    campaign_id: int,
    payload: LootItemUpdate,
    service: StashService = Depends(),
):
    return service.add_loot_item(campaign_id, payload)


@router.delete("/loot/{loot_id}", status_code=204)
def delete_loot_item(
    campaign_id: int,
    loot_id: int,
    service: StashService = Depends(),
):
    service.delete_loot_item(campaign_id, loot_id)
