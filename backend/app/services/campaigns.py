from fastapi import UploadFile
from sqlalchemy import func
from sqlmodel import Session, select

from app.file_storage import (
    build_upload_url,
    delete_uploaded_file,
    save_image_from_uploadfile,
)
from app.models.database import (
    Campaign,
    CharacterProfile,
    Person,
    SessionNote,
)
from app.services.campaign_context import CampaignContext
from app.services.inventory import InventoryService


class CampaignService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def to_response(
        campaign: Campaign,
        session_count: int = 0,
    ) -> dict[str, object]:
        image_url = (
            build_upload_url(campaign.image_path)
            if campaign.image_path
            else ""
        )
        banner_image_url = (
            build_upload_url(campaign.banner_image_path)
            if campaign.banner_image_path
            else image_url
        )
        return {
            "id": campaign.id,
            "name": campaign.name,
            "player_character": campaign.player_character,
            "description": campaign.description,
            "session_count": session_count,
            "image_url": image_url,
            "banner_image_url": banner_image_url,
            "active_character_person_id": (
                campaign.active_character_person_id
            ),
        }

    def get(self, campaign_id: int) -> Campaign:
        return CampaignContext.resolve(
            self.db,
            campaign_id,
        ).campaign

    def count_sessions(self, campaign_id: int) -> int:
        return self.db.exec(
            select(func.count(SessionNote.id)).where(
                SessionNote.campaign_id == campaign_id
            )
        ).one()

    def list_responses(self) -> list[dict[str, object]]:
        results = self.db.exec(
            select(Campaign, func.count(SessionNote.id))
            .join(
                SessionNote,
                SessionNote.campaign_id == Campaign.id,
                isouter=True,
            )
            .group_by(Campaign.id)
            .order_by(Campaign.id)
        ).all()
        return [
            self.to_response(campaign, session_count)
            for campaign, session_count in results
        ]

    def get_response(self, campaign_id: int) -> dict[str, object]:
        campaign = self.get(campaign_id)
        return self.to_response(
            campaign,
            self.count_sessions(campaign_id),
        )

    def stage_create(
        self,
        *,
        name: str,
        player_character: str = "",
        description: str = "",
        image_path: str = "",
        banner_image_path: str = "",
    ) -> Campaign:
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
        context = CampaignContext(self.db, campaign)
        InventoryService(context).stage_ensure_default()
        return campaign

    def create(
        self,
        *,
        name: str,
        player_character: str = "",
        description: str = "",
        image: UploadFile | None = None,
        banner: UploadFile | None = None,
    ) -> dict[str, object]:
        saved_paths: list[str] = []
        try:
            campaign = self.stage_create(
                name=name,
                player_character=player_character,
                description=description,
            )
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
            return self.to_response(campaign)
        except Exception:
            self.db.rollback()
            for path in saved_paths:
                delete_uploaded_file(path)
            raise

    def update(
        self,
        campaign_id: int,
        *,
        name: str,
        player_character: str = "",
        description: str = "",
        image: UploadFile | None = None,
        banner: UploadFile | None = None,
    ) -> dict[str, object]:
        campaign = self.get(campaign_id)
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

        return self.to_response(
            campaign,
            self.count_sessions(campaign_id),
        )

    def delete(self, campaign_id: int) -> dict[str, bool]:
        campaign = self.get(campaign_id)
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
                .where(Person.campaign_id == campaign_id)
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

        return {"deleted": True}
