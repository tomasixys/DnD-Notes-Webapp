from fastapi import APIRouter, Depends, status

from app.dependencies.campaigns import get_campaign_context
from app.models.api import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryRead,
    InventoryUpdate,
    PurseUpdate,
)
from app.services.campaign_context import CampaignContext
from app.services.inventory import InventoryService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/inventory",
    tags=["inventory"],
)


@router.get("", response_model=InventoryRead)
def get_inventory(
    campaign_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> InventoryRead:
    return InventoryService(context).get_default()


@router.patch("", response_model=InventoryRead)
def update_inventory(
    campaign_id: int,
    update: InventoryUpdate,
    context: CampaignContext = Depends(get_campaign_context),
) -> InventoryRead:
    return InventoryService(context).update_metadata(update)


@router.patch("/purse", response_model=InventoryRead)
def update_purse(
    campaign_id: int,
    update: PurseUpdate,
    context: CampaignContext = Depends(get_campaign_context),
) -> InventoryRead:
    return InventoryService(context).update_purse(update)


@router.post(
    "/items",
    response_model=InventoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_item(
    campaign_id: int,
    item_data: InventoryItemCreate,
    context: CampaignContext = Depends(get_campaign_context),
) -> InventoryRead:
    return InventoryService(context).create_item(item_data)


@router.patch("/items/{item_id}", response_model=InventoryRead)
def update_inventory_item(
    campaign_id: int,
    item_id: int,
    update: InventoryItemUpdate,
    context: CampaignContext = Depends(get_campaign_context),
) -> InventoryRead:
    return InventoryService(context).update_item(item_id, update)


@router.delete("/items/{item_id}", response_model=InventoryRead)
def delete_inventory_item(
    campaign_id: int,
    item_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> InventoryRead:
    return InventoryService(context).delete_item(item_id)
