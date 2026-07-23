from fastapi import Depends
from sqlmodel import Session

from app.database import get_session
from app.models.database import Campaign
from app.services.campaign_context import CampaignContext


def get_campaign_context(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> CampaignContext:
    return CampaignContext.resolve(db, campaign_id)


def verify_campaign(campaign_id: int, db: Session) -> Campaign:
    return CampaignContext.resolve(db, campaign_id).campaign
