from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies.campaigns import verify_campaign
from app.models.database import Location
from app.models.api import LocationData, LocationRead
from app.models.enums import RelationshipType, ResourceType
from app.tags import (
    get_resource_tag_reads,
    get_resource_relationship,
    get_resources_referencing_tag,
    handle_tags_of_deleted_resource,
    refresh_reference_tags_for_resource,
    sync_resource_tags,
    sync_resource_relationship,
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
        parent_location=get_resource_relationship(
            db,
            ResourceType.LOCATION,
            location.id,
            RelationshipType.PART_OF,
        ),
        people=get_resources_referencing_tag(
            db,
            location.campaign_id,
            ResourceType.LOCATION,
            location.id,
            ResourceType.PERSON,
            RelationshipType.LOCATED_IN,
        ),
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
    try:
        sync_resource_relationship(
            db,
            campaign_id,
            ResourceType.LOCATION,
            db_location.id,
            RelationshipType.PART_OF,
            ResourceType.LOCATION,
            location.parent_location,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
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
    try:
        sync_resource_relationship(
            db,
            campaign_id,
            ResourceType.LOCATION,
            location.id,
            RelationshipType.PART_OF,
            ResourceType.LOCATION,
            updated_location.parent_location,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
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

    handle_tags_of_deleted_resource(db, ResourceType.LOCATION, location.id)
    db.delete(location)
    db.commit()

    return {"deleted": True}
