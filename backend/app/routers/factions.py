from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, Faction

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/factions",
    tags=["factions"],
)


def ensure_campaign_exists(campaign_id: int, db: Session) -> None:
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")


def get_faction_by_id(
    campaign_id: int,
    faction_id: int,
    db: Session,
) -> Faction | None:
    faction = db.get(Faction, faction_id)

    if faction is None:
        return None

    if faction.campaign_id != campaign_id:
        return None

    return faction


@router.get("")
def get_factions_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    statement = (
        select(Faction)
        .where(Faction.campaign_id == campaign_id)
        .order_by(Faction.name)
    )

    return db.exec(statement).all()


@router.get("/{faction_id}")
def get_faction(
    campaign_id: int,
    faction_id: int,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    faction = get_faction_by_id(
        campaign_id=campaign_id,
        faction_id=faction_id,
        db=db,
    )

    if faction is None:
        raise HTTPException(status_code=404, detail="Faction not found")

    return faction


@router.post("")
def create_faction(
    campaign_id: int,
    faction: Faction,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

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
    ensure_campaign_exists(campaign_id, db)

    faction = get_faction_by_id(
        campaign_id=campaign_id,
        faction_id=faction_id,
        db=db,
    )

    if faction is None:
        raise HTTPException(status_code=404, detail="Faction not found")

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
    ensure_campaign_exists(campaign_id, db)

    faction = get_faction_by_id(
        campaign_id=campaign_id,
        faction_id=faction_id,
        db=db,
    )

    if faction is None:
        raise HTTPException(status_code=404, detail="Faction not found")

    db.delete(faction)
    db.commit()

    return {"deleted": True}