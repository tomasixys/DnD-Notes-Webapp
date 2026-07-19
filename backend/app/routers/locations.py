from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.database import Location
from app.models.api import LocationData, LocationRead
from app.models.enums import ResourceType
from app.routers.campaigns import verify_campaign
from app.tag_handler import (
    get_resource_tag_reads,
    handle_resource_deleted,
    refresh_reference_tags_for_resource,
    sync_resource_tags,
)

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/locations",
    tags=["locations"],
)


def location_to_read(location: Location, db: Session) -> LocationRead:
    return LocationRead(
        id=location.id,
        campaign_id=location.campaign_id,
        name=location.name,
        type=location.type,
        parent_location=location.parent_location,
        description=location.description,
        tags=get_resource_tag_reads(db, ResourceType.LOCATION, location.id),
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
    return [
        location_to_read(location, db)
        for location in get_all_locations_for_campaign(campaign_id, db)
    ]


@router.get("/{location_id}")
def get_location(
    campaign_id: int,
    location_id: int,
    db: Session = Depends(get_session),
):
    return location_to_read(
        get_location_by_id(campaign_id, location_id, db), db
    )


@router.post("")
def create_location(
    campaign_id: int,
    location: LocationData,
    db: Session = Depends(get_session),
):
    verify_campaign(campaign_id, db)

    db_location = Location(
        campaign_id=campaign_id,
        name=location.name,
        type=location.type,
        parent_location=location.parent_location,
        description=location.description,
    )
    db.add(db_location)
    db.flush()
    sync_resource_tags(
        db,
        campaign_id,
        ResourceType.LOCATION,
        db_location.id,
        location.tags,
    )
    refresh_reference_tags_for_resource(
        db, campaign_id, ResourceType.LOCATION, db_location.id
    )
    db.commit()
    db.refresh(db_location)

    return location_to_read(db_location, db)


@router.put("/{location_id}")
def update_location(
    campaign_id: int,
    location_id: int,
    updated_location: LocationData,
    db: Session = Depends(get_session),
):
    location = get_location_by_id(campaign_id, location_id, db)
    previous_name = location.name

    location.name = updated_location.name
    location.type = updated_location.type
    location.parent_location = updated_location.parent_location
    location.description = updated_location.description
    db.add(location)
    db.flush()
    sync_resource_tags(
        db,
        campaign_id,
        ResourceType.LOCATION,
        location.id,
        updated_location.tags,
    )
    refresh_reference_tags_for_resource(
        db,
        campaign_id,
        ResourceType.LOCATION,
        location.id,
        previous_labels=[previous_name],
    )
    db.commit()
    db.refresh(location)

    return location_to_read(location, db)


@router.delete("/{location_id}")
def delete_location(
    campaign_id: int,
    location_id: int,
    db: Session = Depends(get_session),
):
    location = get_location_by_id(campaign_id, location_id, db)

    handle_resource_deleted(db, ResourceType.LOCATION, location.id)
    db.delete(location)
    db.commit()

    return {"deleted": True}
