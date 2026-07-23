from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies.campaigns import verify_campaign
from app.models.database import Faction
from app.models.api import FactionData, FactionRead
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
    prefix="/api/campaigns/{campaign_id}/factions",
    tags=["factions"],
)


def faction_to_read(faction: Faction, db: Session) -> FactionRead:
    return FactionRead(
        id=faction.id,
        campaign_id=faction.campaign_id,
        name=faction.name,
        type=faction.type,
        location=get_resource_relationship(
            db,
            ResourceType.FACTION,
            faction.id,
            RelationshipType.BASED_IN,
        ),
        members=get_resources_referencing_tag(
            db,
            faction.campaign_id,
            ResourceType.FACTION,
            faction.id,
            ResourceType.PERSON,
            RelationshipType.MEMBER_OF,
        ),
        description=faction.description,
        tags=get_resource_tag_reads(db, ResourceType.FACTION, faction.id),
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
    return [
        faction_to_read(faction, db)
        for faction in get_all_factions_for_campaign(campaign_id, db)
    ]


@router.get("/{faction_id}")
def get_faction(
    campaign_id: int,
    faction_id: int,
    db: Session = Depends(get_session),
):
    return faction_to_read(get_faction_by_id(campaign_id, faction_id, db), db)


@router.post("")
def create_faction(
    campaign_id: int,
    faction: FactionData,
    db: Session = Depends(get_session),
):
    verify_campaign(campaign_id, db)

    db_faction = Faction(
        campaign_id=campaign_id,
        name=faction.name,
        type=faction.type,
        description=faction.description,
    )
    db.add(db_faction)
    db.flush()
    sync_resource_tags(
        db,
        campaign_id,
        ResourceType.FACTION,
        db_faction.id,
        faction.tags,
    )
    sync_resource_relationship(
        db,
        campaign_id,
        ResourceType.FACTION,
        db_faction.id,
        RelationshipType.BASED_IN,
        ResourceType.LOCATION,
        faction.location,
    )
    refresh_reference_tags_for_resource(
        db, campaign_id, ResourceType.FACTION, db_faction.id
    )
    db.commit()
    db.refresh(db_faction)

    return faction_to_read(db_faction, db)


@router.put("/{faction_id}")
def update_faction(
    campaign_id: int,
    faction_id: int,
    updated_faction: FactionData,
    db: Session = Depends(get_session),
):
    faction = get_faction_by_id(campaign_id, faction_id, db)
    previous_name = faction.name

    faction.name = updated_faction.name
    faction.type = updated_faction.type
    faction.description = updated_faction.description
    db.add(faction)
    db.flush()
    sync_resource_tags(
        db,
        campaign_id,
        ResourceType.FACTION,
        faction.id,
        updated_faction.tags,
    )
    sync_resource_relationship(
        db,
        campaign_id,
        ResourceType.FACTION,
        faction.id,
        RelationshipType.BASED_IN,
        ResourceType.LOCATION,
        updated_faction.location,
    )
    refresh_reference_tags_for_resource(
        db,
        campaign_id,
        ResourceType.FACTION,
        faction.id,
        previous_labels=[previous_name],
    )
    db.commit()
    db.refresh(faction)

    return faction_to_read(faction, db)


@router.delete("/{faction_id}")
def delete_faction(
    campaign_id: int,
    faction_id: int,
    db: Session = Depends(get_session),
):
    faction = get_faction_by_id(campaign_id, faction_id, db)

    handle_tags_of_deleted_resource(db, ResourceType.FACTION, faction.id)
    db.delete(faction)
    db.commit()

    return {"deleted": True}
