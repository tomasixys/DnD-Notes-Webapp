from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.dependencies.campaigns import verify_campaign
from app.models.api import PersonData
from app.services.people import PersonService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/people",
    tags=["people"],
)


@router.get("")
def get_people_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    people = PersonService(db)
    return [people.to_read(person) for person in people.list(campaign)]


@router.get("/{person_id}")
def get_person(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    people = PersonService(db)
    return people.to_read(people.get(campaign, person_id))


@router.post("")
def create_person(
    campaign_id: int,
    person: PersonData,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    return PersonService(db).create(campaign, person)


@router.put("/{person_id}")
def update_person(
    campaign_id: int,
    person_id: int,
    updated_person: PersonData,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    return PersonService(db).update(campaign, person_id, updated_person)


@router.delete("/{person_id}")
def delete_person(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    PersonService(db).delete(campaign, person_id)
    return {"deleted": True}
