from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.inventory_service import (
    ensure_default_inventory,
    inventory_to_read,
    money_to_copper,
)
from app.models.api import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryRead,
    InventoryUpdate,
    PurseUpdate,
)
from app.models.database import CurrencyBalance, InventoryItem
from app.models.enums import CurrencyDenomination
from app.routers.campaigns import verify_campaign


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/inventory",
    tags=["inventory"],
)


def _get_inventory_item(
    inventory_id: int,
    item_id: int,
    db: Session,
) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None or item.inventory_id != inventory_id:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item


def _commit_and_read(campaign, inventory, db: Session) -> InventoryRead:
    db.commit()
    db.refresh(inventory)
    return inventory_to_read(inventory, campaign, db)


@router.get("", response_model=InventoryRead)
def get_inventory(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    inventory = ensure_default_inventory(campaign, db)
    return _commit_and_read(campaign, inventory, db)


@router.patch("", response_model=InventoryRead)
def update_inventory(
    campaign_id: int,
    update: InventoryUpdate,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    inventory = ensure_default_inventory(campaign, db)

    if "name" in update.model_fields_set:
        name = update.name.strip()
        if not name:
            raise HTTPException(
                status_code=422,
                detail="Inventory name cannot be blank",
            )
        inventory.name = name
    if "description" in update.model_fields_set:
        inventory.description = update.description.strip()

    db.add(inventory)
    return _commit_and_read(campaign, inventory, db)


@router.patch("/purse", response_model=InventoryRead)
def update_purse(
    campaign_id: int,
    update: PurseUpdate,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    inventory = ensure_default_inventory(campaign, db)

    for field_name in update.balances.model_fields_set:
        denomination = CurrencyDenomination(field_name)
        balance = db.get(CurrencyBalance, (inventory.id, denomination))
        balance.amount = getattr(update.balances, field_name)
        db.add(balance)

    return _commit_and_read(campaign, inventory, db)


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
    inventory = ensure_default_inventory(campaign, db)
    name = item_data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Item name cannot be blank")

    try:
        unit_value_cp = (
            money_to_copper(item_data.unit_value)
            if item_data.unit_value is not None
            else None
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    db.add(
        InventoryItem(
            inventory_id=inventory.id,
            name=name,
            description=item_data.description.strip(),
            category=item_data.category,
            rarity=item_data.rarity,
            quantity=item_data.quantity,
            unit_value_cp=unit_value_cp,
        )
    )
    return _commit_and_read(campaign, inventory, db)


@router.patch("/items/{item_id}", response_model=InventoryRead)
def update_inventory_item(
    campaign_id: int,
    item_id: int,
    update: InventoryItemUpdate,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    inventory = ensure_default_inventory(campaign, db)
    item = _get_inventory_item(inventory.id, item_id, db)

    if "name" in update.model_fields_set:
        name = update.name.strip()
        if not name:
            raise HTTPException(
                status_code=422,
                detail="Item name cannot be blank",
            )
        item.name = name
    if "description" in update.model_fields_set:
        item.description = update.description.strip()
    if "category" in update.model_fields_set:
        item.category = update.category
    if "rarity" in update.model_fields_set:
        item.rarity = update.rarity
    if "quantity" in update.model_fields_set:
        item.quantity = update.quantity
    if "unit_value" in update.model_fields_set:
        try:
            item.unit_value_cp = (
                money_to_copper(update.unit_value)
                if update.unit_value is not None
                else None
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    db.add(item)
    return _commit_and_read(campaign, inventory, db)


@router.delete("/items/{item_id}", response_model=InventoryRead)
def delete_inventory_item(
    campaign_id: int,
    item_id: int,
    db: Session = Depends(get_session),
) -> InventoryRead:
    campaign = verify_campaign(campaign_id, db)
    inventory = ensure_default_inventory(campaign, db)
    item = _get_inventory_item(inventory.id, item_id, db)
    db.delete(item)
    return _commit_and_read(campaign, inventory, db)
