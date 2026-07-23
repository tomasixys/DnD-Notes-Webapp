from fastapi import HTTPException
from sqlmodel import Session

from app.models.database import Campaign


def verify_campaign(campaign_id: int, db: Session) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return campaign
