from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, Location
from app.routers.campaigns import verify_campaign

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/locations",
    tags=["locations"],
)

def get_location_by_id(
    campaign_id: int,
    location_id: int,
    db: Session,
) -> Location | None:
    verify_campaign(campaign_id, db)
    location = db.get(Location, location_id)

    if location is None or location.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Location not found")

    return location

def get_all_locations_for_campaign(campaign_id: int, db: Session) -> list[Location]:
    verify_campaign(campaign_id, db)
    statement = (
        select(Location)
        .where(Location.campaign_id == campaign_id)
        .order_by(Location.name)
    )
    return db.exec(statement).all()

@router.get("")
def get_locations_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    return get_all_locations_for_campaign(campaign_id, db)


@router.get("/{location_id}")
def get_location(
    campaign_id: int,
    location_id: int,
    db: Session = Depends(get_session),
):
    return get_location_by_id(campaign_id, location_id, db)


@router.post("")
def create_location(
    campaign_id: int,
    location: Location,
    db: Session = Depends(get_session),
):
    verify_campaign(campaign_id, db)

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
    location = get_location_by_id(campaign_id, location_id, db)

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
    location = get_location_by_id(campaign_id, location_id, db)

    db.delete(location)
    db.commit()

    return {"deleted": True}