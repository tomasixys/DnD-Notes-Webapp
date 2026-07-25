from itertools import count

from sqlmodel import Session, select

from app.auth.enums import SystemRole, UserStatus
from app.auth.models import User
from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignRole
from app.authorization.models import CampaignMembership
from app.models.database import Campaign


_user_sequence = count(1)


def create_user(
    db: Session,
    *,
    role: SystemRole = SystemRole.USER,
    status: UserStatus = UserStatus.ACTIVE,
    can_login: bool = True,
) -> User:
    suffix = next(_user_sequence)
    user = User(
        username=f"test-user-{suffix}",
        normalized_username=f"test-user-{suffix}",
        status=status,
        system_role=role,
        can_login=can_login,
    )
    db.add(user)
    db.flush()
    return user


def campaign_context(
    db: Session,
    campaign: Campaign,
    *,
    role: CampaignRole = CampaignRole.OWNER,
    user: User | None = None,
) -> CampaignContext:
    if campaign.id is None:
        db.add(campaign)
        db.flush()
    if user is None:
        existing = db.exec(
            select(CampaignMembership, User)
            .join(User, User.id == CampaignMembership.user_id)
            .where(CampaignMembership.campaign_id == campaign.id)
            .order_by(CampaignMembership.id)
        ).first()
        if existing is not None:
            membership, existing_user = existing
            return CampaignContext(
                db,
                campaign,
                existing_user,
                membership,
            )
        user = create_user(db)
    membership = CampaignMembership(
        campaign_id=campaign.id,
        user_id=user.id,
        role=role,
        assigned_character_person_id=(
            campaign.active_character_person_id
        ),
        active_character_person_id=campaign.active_character_person_id,
    )
    db.add(membership)
    db.flush()
    return CampaignContext(db, campaign, user, membership)


def resolve_context(
    db: Session,
    campaign_id: int,
) -> CampaignContext:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise AssertionError("Test campaign does not exist")
    return campaign_context(db, campaign)
