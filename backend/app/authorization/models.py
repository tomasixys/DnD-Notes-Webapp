from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Enum as SAEnum,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from app.authorization.enums import CampaignRole


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def role_enum() -> SAEnum:
    return SAEnum(
        CampaignRole,
        values_callable=lambda enum: [member.value for member in enum],
        native_enum=False,
        create_constraint=True,
        name="campaign_role",
    )


class CampaignMembership(SQLModel, table=True):
    __tablename__ = "campaign_membership"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "user_id",
            name="uq_campaign_membership_campaign_user",
        ),
        UniqueConstraint(
            "campaign_id",
            "assigned_character_person_id",
            name="uq_campaign_membership_assigned_character",
        ),
        CheckConstraint(
            "active_character_person_id IS NULL "
            "OR active_character_person_id = assigned_character_person_id",
            name="ck_campaign_membership_active_is_assigned",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        index=True,
    )
    user_id: int = Field(
        foreign_key="app_user.id",
        ondelete="RESTRICT",
        index=True,
    )
    role: CampaignRole = Field(
        default=CampaignRole.MEMBER,
        sa_type=role_enum(),
        index=True,
    )
    assigned_character_person_id: int | None = Field(
        default=None,
        foreign_key="characterprofile.person_id",
        ondelete="SET NULL",
        index=True,
    )
    active_character_person_id: int | None = Field(
        default=None,
        foreign_key="characterprofile.person_id",
        ondelete="SET NULL",
        index=True,
    )
    is_custodial: bool = False
    joined_at: datetime = Field(default_factory=utc_now)


class CampaignInvitation(SQLModel, table=True):
    __tablename__ = "campaign_invitation"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "invited_user_id",
            name="uq_campaign_invitation_campaign_user",
        ),
        UniqueConstraint(
            "token_digest",
            name="uq_campaign_invitation_token_digest",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        index=True,
    )
    invited_user_id: int = Field(
        foreign_key="app_user.id",
        ondelete="CASCADE",
        index=True,
    )
    role: CampaignRole = Field(
        default=CampaignRole.MEMBER,
        sa_type=role_enum(),
    )
    token_digest: str = Field(index=True)
    created_by_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
