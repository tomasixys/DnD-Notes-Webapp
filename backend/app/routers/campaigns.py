from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import func
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, SessionNote
from app.file_storage import build_upload_url, save_campaign_image, delete_uploaded_file

router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)


def campaign_to_response(campaign: Campaign, session_count: int = 0):
    image_url = build_upload_url(campaign.image_path) if campaign.image_path else ""
    banner_image_url = build_upload_url(campaign.banner_image_path) if campaign.banner_image_path else image_url

    return {
        "id": campaign.id,
        "name": campaign.name,
        "player_character": campaign.player_character,
        "description": campaign.description,
        "session_count": session_count,
        "image_url": image_url,
        "banner_image_url": banner_image_url,
    }


@router.get("")
def get_campaigns(db: Session = Depends(get_session)):
    statement = (
        select(Campaign, func.count(SessionNote.id))
        .join(
            SessionNote,
            SessionNote.campaign_id == Campaign.id,
            isouter=True,
        )
        .group_by(Campaign.id)
        .order_by(Campaign.id)
    )

    results = db.exec(statement).all()

    return [
        campaign_to_response(
            campaign=campaign,
            session_count=session_count,
        )
        for campaign, session_count in results
    ]


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_session)):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    statement = (
        select(func.count(SessionNote.id))
        .where(SessionNote.campaign_id == campaign_id)
    )

    session_count = db.exec(statement).one()

    return campaign_to_response(
        campaign=campaign,
        session_count=session_count,
    )


@router.post("")
def create_campaign(
    name: str = Form(...),
    player_character: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    db: Session = Depends(get_session),
):
    campaign = Campaign(
        name=name,
        player_character=player_character,
        description=description,
        image_path="",
        banner_image_path=""
    )

    db.add(campaign)
    db.flush()  # assigns campaign.id without committing yet

    saved_image_relative_path: str | None = None
    saved_banner_relative_path: str | None = None

    try:
        if image is not None and image.filename:
            saved_image_relative_path = save_campaign_image(
                campaign_id=campaign.id,
                file=image,
            )
            campaign.image_path = saved_image_relative_path
        
        if banner is not None and banner.filename:
            saved_banner_relative_path = save_campaign_image(
                campaign_id=campaign.id,
                file=banner,
            )
            campaign.banner_image_path = saved_banner_relative_path

        db.add(campaign)
        db.commit()
        db.refresh(campaign)

    except Exception:
        db.rollback()

        if saved_image_relative_path is not None:
            delete_uploaded_file(saved_image_relative_path)
        if saved_banner_relative_path is not None:
            delete_uploaded_file(saved_banner_relative_path)

        raise

    return campaign_to_response(campaign, session_count=0)


@router.put("/{campaign_id}")
def update_campaign(
    campaign_id: int,
    name: str = Form(...),
    player_character: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    db: Session = Depends(get_session),
):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.name = name
    campaign.player_character = player_character
    campaign.description = description

    old_image_path: str | None = None
    old_banner_path: str | None = None
    saved_image_path: str | None = None
    saved_banner_path: str | None = None

    try:
        if image is not None and image.filename:
            old_image_path = campaign.image_path
            saved_image_path = save_campaign_image(
                campaign_id=campaign.id,
                file=image,
            )
            campaign.image_path = saved_image_path

        if banner is not None and banner.filename:
            old_banner_path = campaign.banner_image_path
            saved_banner_path = save_campaign_image(
                campaign_id=campaign.id,
                file=banner,
            )
            campaign.banner_image_path = saved_banner_path

        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        if old_image_path is not None:
            delete_uploaded_file(old_image_path)

        if old_banner_path is not None:
            delete_uploaded_file(old_banner_path)

    except Exception:
        db.rollback()

        if saved_image_path is not None:
            delete_uploaded_file(saved_image_path)

        if saved_banner_path is not None:
            delete_uploaded_file(saved_banner_path)

        raise

    statement = (
        select(func.count(SessionNote.id))
        .where(SessionNote.campaign_id == campaign_id)
    )

    session_count = db.exec(statement).one()

    return campaign_to_response(
        campaign=campaign,
        session_count=session_count,
    )


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int, 
    db: Session = Depends(get_session)
):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    image_path = campaign.image_path
    banner_path = campaign.banner_image_path

    db.delete(campaign)
    db.commit()

    if image_path:
        delete_uploaded_file(image_path)

    if banner_path and banner_path != image_path:
        delete_uploaded_file(banner_path)

    return {"deleted": True}