from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlmodel import Session

from app.database import get_session
from app.models.api import CampaignRead, DeleteResponse
from app.services.campaigns import CampaignService


router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)


@router.get("")
def get_campaigns(
    db: Session = Depends(get_session),
) -> list[CampaignRead]:
    return CampaignService(db).list_reads()


@router.get("/{campaign_id}")
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> CampaignRead:
    return CampaignService(db).get_read(campaign_id)


@router.post("")
def create_campaign(
    name: str = Form(...),
    description: str = Form(""),
    character_name: str = Form(""),
    faction_name: str = Form(""),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    db: Session = Depends(get_session),
) -> CampaignRead:
    return CampaignService(db).create(
        name=name,
        description=description,
        character_name=character_name,
        faction_name=faction_name,
        image=image,
        banner=banner,
    )


@router.put("/{campaign_id}")
def update_campaign(
    campaign_id: int,
    name: str = Form(...),
    description: str = Form(""),
    active_character_person_id: int | None = Form(None),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    db: Session = Depends(get_session),
) -> CampaignRead:
    return CampaignService(db).update(
        campaign_id,
        name=name,
        description=description,
        active_character_person_id=active_character_person_id,
        image=image,
        banner=banner,
    )


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> DeleteResponse:
    return CampaignService(db).delete(campaign_id)
