from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign

router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)


@router.get("")
def get_campaigns(db: Session = Depends(get_session)):
    statement = select(Campaign).order_by(Campaign.id)
    return db.exec(statement).all()


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_session)):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return campaign


@router.post("")
def create_campaign(campaign: Campaign, db: Session = Depends(get_session)):
    campaign.id = None

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign


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

    return campaign


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_session)):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    db.delete(campaign)
    db.commit()

    return {"deleted": True}