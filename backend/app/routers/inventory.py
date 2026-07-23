from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies.campaigns import verify_campaign
from app.models.api import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryRead,
    InventoryUpdate,
    PurseUpdate,
)
from app.services.inventory import InventoryService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/inventory",
    tags=["inventory"],
)


@router.get("", response_model=InventoryRead)
def get_inventory(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    return InventoryService(db).get_default(campaign)


@router.patch("", response_model=InventoryRead)
def update_inventory(
    campaign_id: int,
    update: InventoryUpdate,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    return InventoryService(db).update_metadata(campaign, update)


@router.patch("/purse", response_model=InventoryRead)
def update_purse(
    campaign_id: int,
    update: PurseUpdate,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    return InventoryService(db).update_purse(campaign, update)


@router.post(
    "/items",
    response_model=InventoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_item(
    campaign_id: int,
    item_data: InventoryItemCreate,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    return InventoryService(db).create_item(campaign, item_data)


@router.patch("/items/{item_id}", response_model=InventoryRead)
def update_inventory_item(
    campaign_id: int,
    item_id: int,
    update: InventoryItemUpdate,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    return InventoryService(db).update_item(
        campaign,
        item_id,
        update,
    )


@router.delete("/items/{item_id}", response_model=InventoryRead)
def delete_inventory_item(
    campaign_id: int,
    item_id: int,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    return InventoryService(db).delete_item(campaign, item_id)
