from fastapi import APIRouter, Depends

from app.dependencies.campaigns import get_campaign_context
from app.models.api import DeleteResponse, LocationData, LocationRead
from app.services.campaign_context import CampaignContext
from app.services.locations import LocationService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/locations",
    tags=["locations"],
)


@router.get("")
def get_locations_for_campaign(
    context: CampaignContext = Depends(get_campaign_context),
):
    locations = LocationService(context)
    return [locations.to_read(location) for location in locations.list()]


@router.get("/{location_id}")
def get_location(
    location_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    locations = LocationService(context)
    return locations.to_read(locations.get(location_id))


@router.post("")
def create_location(
    location: LocationData,
    context: CampaignContext = Depends(get_campaign_context),
) -> LocationRead:
    return LocationService(context).create(location)


@router.put("/{location_id}")
def update_location(
    location_id: int,
    updated_location: LocationData,
    context: CampaignContext = Depends(get_campaign_context),
) -> LocationRead:
    return LocationService(context).update(
        location_id,
        updated_location,
    )


@router.delete("/{location_id}")
def delete_location(
    location_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> DeleteResponse:
    return LocationService(context).delete(location_id)
