from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, Person

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/people",
    tags=["people"],
)


def ensure_campaign_exists(campaign_id: int, db: Session) -> None:
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")


def get_person_by_id(
    campaign_id: int,
    person_id: int,
    db: Session,
) -> Person | None:
    person = db.get(Person, person_id)

    if person is None:
        return None

    if person.campaign_id != campaign_id:
        return None

    return person


@router.get("")
def get_people_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    statement = (
        select(Person)
        .where(Person.campaign_id == campaign_id)
        .order_by(Person.name)
    )

    return db.exec(statement).all()


@router.get("/{person_id}")
def get_person(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

    person = get_person_by_id(
        campaign_id=campaign_id,
        person_id=person_id,
        db=db,
    )

    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    return person


@router.post("")
def create_person(
    campaign_id: int,
    person: Person,
    db: Session = Depends(get_session),
):
    ensure_campaign_exists(campaign_id, db)

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
    ensure_campaign_exists(campaign_id, db)

    person = get_person_by_id(
        campaign_id=campaign_id,
        person_id=person_id,
        db=db,
    )

    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

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
    ensure_campaign_exists(campaign_id, db)

    person = get_person_by_id(
        campaign_id=campaign_id,
        person_id=person_id,
        db=db,
    )

    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    db.delete(person)
    db.commit()

    return {"deleted": True}