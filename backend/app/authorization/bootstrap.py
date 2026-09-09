from sqlmodel import Session, select

from app.auth.administration import LOCAL_USER_USERNAME
from app.auth.models import User
from app.authorization.enums import CampaignRole
from app.authorization.models import CampaignMembership
from app.models.database import Campaign


class MembershipBootstrapService:
    """Idempotently claim legacy local campaigns for the local identity."""

    def __init__(self, db: Session):
        self.db = db

    def ensure_local_ownership(self) -> int:
        local_user = self.db.exec(
            select(User).where(
                User.normalized_username == LOCAL_USER_USERNAME
            )
        ).first()
        if local_user is None:
            raise RuntimeError(
                "Local identity must exist before campaign ownership "
                "backfill."
            )

        campaigns = self.db.exec(
            select(Campaign).order_by(Campaign.id)
        ).all()
        created = 0
        for campaign in campaigns:
            membership = self.db.exec(
                select(CampaignMembership).where(
                    CampaignMembership.campaign_id == campaign.id,
                    CampaignMembership.user_id == local_user.id,
                )
            ).first()
            if membership is not None:
                continue
            membership = CampaignMembership(
                campaign_id=campaign.id,
                user_id=local_user.id,
                role=CampaignRole.OWNER,
                assigned_character_person_id=(
                    campaign.active_character_person_id
                ),
                active_character_person_id=(
                    campaign.active_character_person_id
                ),
            )
            self.db.add(membership)
            created += 1
        self.db.commit()
        return created
