from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.authorization.context import CampaignContext
from app.authorization.dependencies import get_shared_read_context
from app.file_storage import resolve_stored_image
from app.services.characters import CharacterService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/assets",
    tags=["assets"],
)

PRIVATE_ASSET_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
}
IMAGE_RESPONSE = {
    200: {
        "content": {
            "image/*": {
                "schema": {
                    "type": "string",
                    "format": "binary",
                }
            }
        },
        "description": "Authorized campaign image.",
    }
}


class CampaignAssetKind(str, Enum):
    IMAGE = "image"
    BANNER = "banner"


def image_response(relative_path: str) -> FileResponse:
    if not relative_path:
        raise HTTPException(status_code=404, detail="Asset not found.")
    stored = resolve_stored_image(relative_path)
    return FileResponse(
        stored.path,
        media_type=stored.media_type,
        headers=PRIVATE_ASSET_HEADERS,
    )


@router.get(
    "/{asset_kind}",
    response_class=FileResponse,
    responses=IMAGE_RESPONSE,
)
def get_campaign_asset(
    asset_kind: CampaignAssetKind,
    context: CampaignContext = Depends(get_shared_read_context),
) -> FileResponse:
    relative_path = (
        context.campaign.image_path
        if asset_kind is CampaignAssetKind.IMAGE
        else context.campaign.banner_image_path
    )
    return image_response(relative_path)


@router.get(
    "/characters/{person_id}/portrait",
    response_class=FileResponse,
    responses=IMAGE_RESPONSE,
)
def get_character_portrait(
    person_id: int,
    context: CampaignContext = Depends(get_shared_read_context),
) -> FileResponse:
    profile = CharacterService(context).get_profile(person_id)
    return image_response(profile.image_path)
