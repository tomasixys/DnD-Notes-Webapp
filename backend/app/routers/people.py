from fastapi import APIRouter, Depends

from app.dependencies.campaigns import get_campaign_context
from app.models.api import DeleteResponse, PersonData, PersonRead
from app.services.campaign_context import CampaignContext
from app.services.people import PersonService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/people",
    tags=["people"],
)


@router.get("")
def get_people_for_campaign(
    context: CampaignContext = Depends(get_campaign_context),
) -> list[PersonRead]:
    people = PersonService(context)
    return [people.to_read(person) for person in people.list()]


@router.get("/{person_id}")
def get_person(
    person_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> PersonRead:
    people = PersonService(context)
    return people.to_read(people.get(person_id))


@router.post("")
def create_person(
    person: PersonData,
    context: CampaignContext = Depends(get_campaign_context),
) -> PersonRead:
    return PersonService(context).create(person)


@router.put("/{person_id}")
def update_person(
    person_id: int,
    updated_person: PersonData,
    context: CampaignContext = Depends(get_campaign_context),
) -> PersonRead:
    return PersonService(context).update(person_id, updated_person)


@router.delete("/{person_id}")
def delete_person(
    person_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> DeleteResponse:
    return PersonService(context).delete(person_id)
