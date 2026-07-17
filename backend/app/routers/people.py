from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, Person
from app.routers.campaigns import verify_campaign

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/people",
    tags=["people"],
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
    return get_all_people_for_campaign(campaign_id, db)


@router.get("/{person_id}")
def get_person(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    return get_person_by_id(campaign_id, person_id, db)


@router.post("")
def create_person(
    campaign_id: int,
    person: Person,
    db: Session = Depends(get_session),
):
    verify_campaign(campaign_id, db)

    person.id = None
    person.campaign_id = campaign_id

    db.add(person)
    db.commit()
    db.refresh(person)

    return person


@router.put("/{person_id}")
def update_person(
    campaign_id: int,
    person_id: int,
    updated_person: Person,
    db: Session = Depends(get_session),
):
    person = get_person_by_id(campaign_id, person_id, db)

    person.name = updated_person.name
    person.role = updated_person.role
    person.faction = updated_person.faction
    person.location = updated_person.location
    person.description = updated_person.description
    person.tags = updated_person.tags

    db.add(person)
    db.commit()
    db.refresh(person)

    return person


@router.delete("/{person_id}")
def delete_person(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    person = get_person_by_id(campaign_id, person_id, db)

    db.delete(person)
    db.commit()

    return {"deleted": True}