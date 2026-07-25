from fastapi import UploadFile
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.models import User
from app.authorization.capabilities import ROLE_CAPABILITIES
from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignCapability, CampaignRole
from app.authorization.models import CampaignMembership
from app.file_storage import (
    build_campaign_asset_url,
    delete_uploaded_file,
    save_image_from_uploadfile,
)
from app.models.api import CampaignRead, DeleteResponse
from app.models.database import (
    Campaign,
    CharacterProfile,
    Person,
    Episode,
)
from app.services.inventory import InventoryService


class CampaignService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    @staticmethod
    def to_read(
        campaign: Campaign,
        membership: CampaignMembership,
        session_count: int = 0,
    ) -> CampaignRead:
        image_url = (
            build_campaign_asset_url(campaign.id, "image")
            if campaign.image_path
            else ""
        )
        banner_image_url = (
            build_campaign_asset_url(campaign.id, "banner")
            if campaign.banner_image_path
            else image_url
        )
        return CampaignRead(
            id=campaign.id,
            name=campaign.name,
            player_character=campaign.player_character,
            description=campaign.description,
            session_count=session_count,
            image_url=image_url,
            banner_image_url=banner_image_url,
            active_character_person_id=(
                membership.active_character_person_id
            ),
            assigned_character_person_id=(
                membership.assigned_character_person_id
            ),
            membership_role=membership.role,
            capabilities=sorted(
                ROLE_CAPABILITIES[membership.role],
                key=lambda capability: capability.value,
            ),
        )

    def get_context(self, campaign_id: int) -> CampaignContext:
        return CampaignContext.resolve(
            self.db,
            campaign_id,
            self.user,
        )

    def count_episodes(self, campaign_id: int) -> int:
        return self.db.exec(
            select(func.count(Episode.id)).where(
                Episode.campaign_id == campaign_id
            )
        ).one()

    def list_reads(self) -> list[CampaignRead]:
        results = self.db.exec(
            select(
                Campaign,
                CampaignMembership,
                func.count(Episode.id),
            )
            .join(
                CampaignMembership,
                CampaignMembership.campaign_id == Campaign.id,
            )
            .join(
                Episode,
                Episode.campaign_id == Campaign.id,
                isouter=True,
            )
            .where(
                CampaignMembership.user_id == self.user.id,
                CampaignMembership.is_custodial.is_(False),
                Campaign.orphaned.is_(False),
            )
            .group_by(Campaign.id, CampaignMembership.id)
            .order_by(Campaign.id)
        ).all()
        return [
            self.to_read(campaign, membership, session_count)
            for campaign, membership, session_count in results
        ]

    def get_read(self, campaign_id: int) -> CampaignRead:
        context = self.get_context(campaign_id)
        return self.to_read(
            context.campaign,
            context.membership,
            self.count_episodes(campaign_id),
        )

    def stage_create(
        self,
        *,
        name: str,
        player_character: str = "",
        description: str = "",
        image_path: str = "",
        banner_image_path: str = "",
    ) -> CampaignContext:
        """Create a campaign aggregate in the caller-owned transaction."""
        campaign = Campaign(
            name=name,
            player_character=player_character,
            description=description,
            image_path=image_path,
            banner_image_path=banner_image_path,
        )
        self.db.add(campaign)
        self.db.flush()
        membership = CampaignMembership(
            campaign_id=campaign.id,
            user_id=self.user.id,
            role=CampaignRole.OWNER,
        )
        self.db.add(membership)
        self.db.flush()
        context = CampaignContext(
            self.db,
            campaign,
            self.user,
            membership,
        )
        InventoryService(context).stage_ensure_default()
        return context

    def create(
        self,
        *,
        name: str,
        player_character: str = "",
        description: str = "",
        image: UploadFile | None = None,
        banner: UploadFile | None = None,
    ) -> CampaignRead:
        saved_paths: list[str] = []
        try:
            context = self.stage_create(
                name=name,
                player_character=player_character,
                description=description,
            )
            campaign = context.campaign
            if image is not None and image.filename:
                campaign.image_path = save_image_from_uploadfile(
                    campaign.id,
                    image,
                )
                saved_paths.append(campaign.image_path)
            if banner is not None and banner.filename:
                campaign.banner_image_path = save_image_from_uploadfile(
                    campaign.id,
                    banner,
                )
                saved_paths.append(campaign.banner_image_path)

            self.db.add(campaign)
            self.db.commit()
            self.db.refresh(campaign)
            return self.to_read(campaign, context.membership)
        except Exception:
            self.db.rollback()
            for path in saved_paths:
                delete_uploaded_file(path)
            raise

    def update(
        self,
        context: CampaignContext,
        *,
        name: str,
        player_character: str = "",
        description: str = "",
        image: UploadFile | None = None,
        banner: UploadFile | None = None,
    ) -> CampaignRead:
        context.require(CampaignCapability.CAMPAIGN_UPDATE)
        campaign = context.campaign
        old_paths = {
            path
            for path in (
                campaign.image_path,
                campaign.banner_image_path,
            )
            if path
        }
        saved_paths: list[str] = []

        try:
            campaign.name = name
            campaign.player_character = player_character
            campaign.description = description

            if image is not None and image.filename:
                campaign.image_path = save_image_from_uploadfile(
                    campaign.id,
                    image,
                )
                saved_paths.append(campaign.image_path)
            if banner is not None and banner.filename:
                campaign.banner_image_path = save_image_from_uploadfile(
                    campaign.id,
                    banner,
                )
                saved_paths.append(campaign.banner_image_path)

            self.db.add(campaign)
            self.db.commit()
            self.db.refresh(campaign)
        except Exception:
            self.db.rollback()
            for path in saved_paths:
                delete_uploaded_file(path)
            raise

        retained_paths = {
            path
            for path in (
                campaign.image_path,
                campaign.banner_image_path,
            )
            if path
        }
        for path in old_paths - retained_paths:
            delete_uploaded_file(path)

        return self.to_read(
            campaign,
            context.membership,
            self.count_episodes(context.campaign_id),
        )

    def delete(self, context: CampaignContext) -> DeleteResponse:
        context.require(CampaignCapability.CAMPAIGN_DELETE)
        campaign = context.campaign
        uploaded_paths = {
            path
            for path in (
                campaign.image_path,
                campaign.banner_image_path,
            )
            if path
        }
        uploaded_paths.update(
            profile.image_path
            for profile in self.db.exec(
                select(CharacterProfile)
                .join(
                    Person,
                    Person.id == CharacterProfile.person_id,
                )
                .where(Person.campaign_id == context.campaign_id)
            ).all()
            if profile.image_path
        )

        try:
            self.db.delete(campaign)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        for path in uploaded_paths:
            delete_uploaded_file(path)

        return DeleteResponse(deleted_id=context.campaign_id)
