from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, Faction
from app.routers.campaigns import verify_campaign

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/factions",
    tags=["factions"],
)

def get_faction_by_id(
    campaign_id: int,
    faction_id: int,
    db: Session,
) -> Faction | None:
    verify_campaign(campaign_id, db)
    faction = db.get(Faction, faction_id)

    if faction is None or faction.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Faction not found")

    return faction

def get_all_factions_for_campaign(campaign_id: int, db: Session) -> list[Faction]:
    verify_campaign(campaign_id, db)
    statement = (
        select(Faction)
        .where(Faction.campaign_id == campaign_id)
        .order_by(Faction.name)
    )
    return db.exec(statement).all()

@router.get("")
def get_factions_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    return get_all_factions_for_campaign(campaign_id, db)


@router.get("/{faction_id}")
def get_faction(
    campaign_id: int,
    faction_id: int,
    db: Session = Depends(get_session),
):
    return get_faction_by_id(campaign_id, faction_id, db)


@router.post("")
def create_faction(
    campaign_id: int,
    faction: Faction,
    db: Session = Depends(get_session),
):
    verify_campaign(campaign_id, db)

    faction.id = None
    faction.campaign_id = campaign_id

    db.add(faction)
    db.commit()
    db.refresh(faction)

    return faction


@router.put("/{faction_id}")
def update_faction(
    campaign_id: int,
    faction_id: int,
    updated_faction: Faction,
    db: Session = Depends(get_session),
):
    faction = get_faction_by_id(campaign_id, faction_id, db)

    faction.name = updated_faction.name
    faction.type = updated_faction.type
    faction.location = updated_faction.location
    faction.description = updated_faction.description
    faction.tags = updated_faction.tags

    db.add(faction)
    db.commit()
    db.refresh(faction)

    return faction


@router.delete("/{faction_id}")
def delete_faction(
    campaign_id: int,
    faction_id: int,
    db: Session = Depends(get_session),
):
    faction = get_faction_by_id(campaign_id, faction_id, db)

    db.delete(faction)
    db.commit()

    return {"deleted": True}