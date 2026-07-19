from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.database.models import Person
from app.api.models import PersonData, PersonRead, ResourceType
from app.routers.campaigns import verify_campaign
from app.tag_handler import (
    get_resource_tag_reads,
    handle_resource_deleted,
    resolve_pending_tags_for_resource,
    sync_resource_tags,
)

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/people",
    tags=["people"],
)


def person_to_read(person: Person, db: Session) -> PersonRead:
    return PersonRead(
        id=person.id,
        campaign_id=person.campaign_id,
        name=person.name,
        role=person.role,
        faction=person.faction,
        location=person.location,
        description=person.description,
        tags=get_resource_tag_reads(db, ResourceType.PERSON, person.id),
    )


def get_person_by_id(
    campaign_id: int,
    person_id: int,
    db: Session,
) -> Person | None:
    verify_campaign(campaign_id, db)
    person = db.get(Person, person_id)

    if person is None or person.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Person not found")

    return person

def get_all_people_for_campaign(campaign_id: int, db: Session) -> list[Person]:
    verify_campaign(campaign_id, db)
    statement = (
        select(Person)
        .where(Person.campaign_id == campaign_id)
        .order_by(Person.name)
    )
    return db.exec(statement).all()

@router.get("")
def get_people_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    return [
        person_to_read(person, db)
        for person in get_all_people_for_campaign(campaign_id, db)
    ]


@router.get("/{person_id}")
def get_person(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    return person_to_read(get_person_by_id(campaign_id, person_id, db), db)


@router.post("")
def create_person(
    campaign_id: int,
    person: PersonData,
    db: Session = Depends(get_session),
):
    verify_campaign(campaign_id, db)

    db_person = Person(
        campaign_id=campaign_id,
        name=person.name,
        role=person.role,
        faction=person.faction,
        location=person.location,
        description=person.description,
    )
    db.add(db_person)
    db.flush()
    sync_resource_tags(
        db, campaign_id, ResourceType.PERSON, db_person.id, person.tags
    )
    resolve_pending_tags_for_resource(
        db, campaign_id, ResourceType.PERSON, db_person.name
    )
    db.commit()
    db.refresh(db_person)

    return person_to_read(db_person, db)


@router.put("/{person_id}")
def update_person(
    campaign_id: int,
    person_id: int,
    updated_person: PersonData,
    db: Session = Depends(get_session),
):
    person = get_person_by_id(campaign_id, person_id, db)

    person.name = updated_person.name
    person.role = updated_person.role
    person.faction = updated_person.faction
    person.location = updated_person.location
    person.description = updated_person.description
    db.add(person)
    db.flush()
    sync_resource_tags(
        db, campaign_id, ResourceType.PERSON, person.id, updated_person.tags
    )
    resolve_pending_tags_for_resource(
        db, campaign_id, ResourceType.PERSON, person.name
    )
    db.commit()
    db.refresh(person)

    return person_to_read(person, db)


@router.delete("/{person_id}")
def delete_person(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    person = get_person_by_id(campaign_id, person_id, db)

    handle_resource_deleted(db, ResourceType.PERSON, person.id)
    db.delete(person)
    db.commit()

    return {"deleted": True}
