from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, Location

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/locations",
    tags=["locations"],
)


def ensure_campaign_exists(campaign_id: int, db: Session) -> None:
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")


def get_location_by_id(
    campaign_id: int,
    location_id: int,
    db: Session,
) -> Location | None:
    location = db.get(Location, location_id)

    if location is None:
        return None

    if location.campaign_id != campaign_id:
        return None

    return location


@router.get("")
def get_locations_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    statement = (
        select(Location)
        .where(Location.campaign_id == campaign_id)
        .order_by(Location.name)
    )

    return db.exec(statement).all()


@router.get("/{location_id}")
def get_location(
    campaign_id: int,
    location_id: int,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    location = get_location_by_id(
        campaign_id=campaign_id,
        location_id=location_id,
        db=db,
    )

    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    return location


@router.post("")
def create_location(
    campaign_id: int,
    location: Location,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    location.id = None
    location.campaign_id = campaign_id

    db.add(location)
    db.commit()
    db.refresh(location)

    return location


@router.put("/{location_id}")
def update_location(
    campaign_id: int,
    location_id: int,
    updated_location: Location,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    location = get_location_by_id(
        campaign_id=campaign_id,
        location_id=location_id,
        db=db,
    )

    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    location.name = updated_location.name
    location.type = updated_location.type
    location.parent_location = updated_location.parent_location
    location.description = updated_location.description
    location.tags = updated_location.tags

    db.add(location)
    db.commit()
    db.refresh(location)

    return location


@router.delete("/{location_id}")
def delete_location(
    campaign_id: int,
    location_id: int,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    location = get_location_by_id(
        campaign_id=campaign_id,
        location_id=location_id,
        db=db,
    )

    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    db.delete(location)
    db.commit()

    return {"deleted": True}