from fastapi import UploadFile
from sqlalchemy import func
from sqlmodel import Session, select

from app.file_storage import (
    build_upload_url,
    delete_uploaded_file,
    save_image_from_uploadfile,
)
from app.models.api import (
    ActiveCharacterRef,
    CampaignRead,
    DeleteResponse,
    FactionData,
    PersonData,
)
from app.models.database import (
    Campaign,
    CharacterProfile,
    Person,
    SessionNote,
)
from app.services.campaign_context import CampaignContext
from app.services.characters import CharacterService
from app.services.factions import FactionService
from app.services.inventory import InventoryService
from app.services.people import PersonService


class CampaignService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def to_read(
        campaign: Campaign,
        session_count: int = 0,
        active_character: ActiveCharacterRef | None = None,
    ) -> CampaignRead:
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
        return CampaignRead(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            session_count=session_count,
            image_url=image_url,
            banner_image_url=banner_image_url,
            active_character=active_character,
        )

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

    def list_reads(self) -> list[CampaignRead]:
        results = self.db.exec(
            select(Campaign, func.count(SessionNote.id), Person.id, Person.name)
            .join(
                SessionNote,
                SessionNote.campaign_id == Campaign.id,
                isouter=True,
            )
            .join(
                Person,
                Person.id == Campaign.active_character_person_id,
                isouter=True,
            )
            .group_by(Campaign.id, Person.id, Person.name)
            .order_by(Campaign.id)
        ).all()
        return [
            self.to_read(
                campaign,
                session_count,
                active_character=(
                    ActiveCharacterRef(id=person_id, name=person_name)
                    if person_id is not None and person_name is not None
                    else None
                ),
            )
            for campaign, session_count, person_id, person_name in results
        ]

    def get_read(self, campaign_id: int) -> CampaignRead:
        campaign = self.get(campaign_id)
        active_character = None
        if campaign.active_character_person_id is not None:
            person = self.db.get(Person, campaign.active_character_person_id)
            if person is not None:
                active_character = ActiveCharacterRef(
                    id=person.id,
                    name=person.name,
                )
        return self.to_read(
            campaign,
            self.count_sessions(campaign_id),
            active_character=active_character,
        )

    def stage_create(
        self,
        *,
        name: str,
        description: str = "",
        image_path: str = "",
        banner_image_path: str = "",
    ) -> Campaign:
        """Create a campaign aggregate in the caller-owned transaction."""
        campaign = Campaign(
            name=name,
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
        description: str = "",
        character_name: str = "",
        faction_name: str = "",
        image: UploadFile | None = None,
        banner: UploadFile | None = None,
    ) -> CampaignRead:
        saved_paths: list[str] = []
        try:
            campaign = self.stage_create(
                name=name,
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

            context = CampaignContext(self.db, campaign)
            created_faction_name = ""
            if faction_name and faction_name.strip():
                created_faction_name = faction_name.strip()
                FactionService(context).stage_create(
                    FactionData(name=created_faction_name)
                )

            if character_name and character_name.strip():
                person = PersonService(context).stage_create(
                    PersonData(
                        name=character_name.strip(),
                        faction=created_faction_name,
                    )
                )
                CharacterService(context).stage_create_profile(person.id)
                campaign.active_character_person_id = person.id

            self.db.add(campaign)
            self.db.commit()
            self.db.refresh(campaign)
            return self.get_read(campaign.id)
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
        description: str = "",
        active_character_person_id: int | None = None,
        image: UploadFile | None = None,
        banner: UploadFile | None = None,
    ) -> CampaignRead:
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
            campaign.description = description

            if active_character_person_id is not None and active_character_person_id > 0:
                context = CampaignContext(self.db, campaign)
                person = PersonService(context).get(active_character_person_id)
                if self.db.get(CharacterProfile, person.id) is None:
                    CharacterService(context).stage_create_profile(person.id)
                campaign.active_character_person_id = person.id
            elif active_character_person_id == 0:
                campaign.active_character_person_id = None

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

        return self.get_read(campaign_id)

    def delete(self, campaign_id: int) -> DeleteResponse:
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

        return DeleteResponse(deleted_id=campaign_id)
