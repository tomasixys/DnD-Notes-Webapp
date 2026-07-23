from dataclasses import dataclass

from fastapi import HTTPException
from sqlmodel import Session

from app.models.database import Campaign


@dataclass(frozen=True)
class CampaignContext:
    """A verified campaign and its request-scoped database session."""

    db: Session
    campaign: Campaign

    def __post_init__(self) -> None:
        if self.campaign.id is None:
            raise ValueError(
                "CampaignContext requires a flushed campaign"
            )

    @property
    def campaign_id(self) -> int:
        return self.campaign.id

    @classmethod
    def resolve(
        cls,
        db: Session,
        campaign_id: int,
    ) -> "CampaignContext":
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return cls(db=db, campaign=campaign)
