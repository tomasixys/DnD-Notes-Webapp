from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlmodel import Session

from app.auth.dependencies import require_current_user
from app.auth.models import User
from app.authorization.context import CampaignContext
from app.authorization.dependencies import (
    get_campaign_delete_context,
    get_campaign_update_context,
)
from app.database import get_session
from app.models.api import CampaignRead, DeleteResponse
from app.services.campaigns import CampaignService


router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)


@router.get("")
def get_campaigns(
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> list[CampaignRead]:
    return CampaignService(db, user).list_reads()


@router.get("/{campaign_id}")
def get_campaign(
    campaign_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> CampaignRead:
    return CampaignService(db, user).get_read(campaign_id)


@router.post("")
def create_campaign(
    name: str = Form(...),
    player_character: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> CampaignRead:
    return CampaignService(db, user).create(
        name=name,
        player_character=player_character,
        description=description,
        image=image,
        banner=banner,
    )


@router.put("/{campaign_id}")
def update_campaign(
    name: str = Form(...),
    player_character: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    context: CampaignContext = Depends(get_campaign_update_context),
) -> CampaignRead:
    return CampaignService(context.db, context.user).update(
        context,
        name=name,
        player_character=player_character,
        description=description,
        image=image,
        banner=banner,
    )


@router.delete("/{campaign_id}")
def delete_campaign(
    context: CampaignContext = Depends(get_campaign_delete_context),
) -> DeleteResponse:
    return CampaignService(context.db, context.user).delete(context)
