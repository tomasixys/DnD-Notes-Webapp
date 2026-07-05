from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, SessionNote

router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)


def campaign_to_response(campaign: Campaign, session_count: int = 0):
    return {
        "id": campaign.id,
        "name": campaign.name,
        "player_character": campaign.player_character,
        "description": campaign.description,
        "session_count": session_count,
        "image_url": campaign.image_url,
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
def create_campaign(campaign: Campaign, db: Session = Depends(get_session)):
    campaign.id = None

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign_to_response(campaign, session_count=0)


@router.put("/{campaign_id}")
def update_campaign(
    campaign_id: int,
    updated_campaign: Campaign,
    db: Session = Depends(get_session),
):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.name = updated_campaign.name
    campaign.player_character = updated_campaign.player_character
    campaign.description = updated_campaign.description
    campaign.image_url = updated_campaign.image_url

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

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
def delete_campaign(campaign_id: int, db: Session = Depends(get_session)):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    db.delete(campaign)
    db.commit()

    return {"deleted": True}