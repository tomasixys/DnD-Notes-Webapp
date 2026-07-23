from fastapi import HTTPException
from sqlmodel import Session, select

from app.file_storage import build_upload_url, delete_uploaded_file
from app.models.api import CharacterCreate, CharacterRead, CharacterUpdate
from app.models.database import (
    BackstoryNote,
    Campaign,
    CharacterNote,
    CharacterProfile,
)
from app.models.enums import ResourceType
from app.services.inventory import InventoryService
from app.services.people import PersonService
from app.tags import handle_tags_of_deleted_resource


class CharacterService:
    def __init__(
        self,
        db: Session,
        people: PersonService | None = None,
        inventory: InventoryService | None = None,
    ):
        self.db = db
        self.people = people or PersonService(db)
        self.inventory = inventory or InventoryService(db)

    def to_read(
        self,
        profile: CharacterProfile,
        campaign: Campaign,
    ) -> CharacterRead:
        person = self.people.get(campaign, profile.person_id)
        return CharacterRead(
            person=self.people.to_read(person),
            short_bio=profile.short_bio,
            appearance=profile.appearance,
            image_url=(
                build_upload_url(profile.image_path)
                if profile.image_path
                else ""
            ),
            is_active=(
                campaign.active_character_person_id == profile.person_id
            ),
        )

    def get_profile(
        self,
        campaign: Campaign,
        person_id: int,
    ) -> CharacterProfile:
        self.people.get(campaign, person_id)
        profile = self.db.get(CharacterProfile, person_id)
        if profile is None:
            raise HTTPException(
                status_code=404,
                detail="Character profile not found",
            )
        return profile

    def get_active(self, campaign: Campaign) -> CharacterRead | None:
        if campaign.active_character_person_id is None:
            return None

        profile = self.db.get(
            CharacterProfile,
            campaign.active_character_person_id,
        )
        if profile is None:
            campaign.active_character_person_id = None
            self.db.add(campaign)
            self.db.commit()
            return None

        return self.to_read(profile, campaign)

    def stage_create_profile(
        self,
        campaign: Campaign,
        person_id: int,
        *,
        short_bio: str = "",
        appearance: str = "",
        image_path: str = "",
    ) -> CharacterProfile:
        """Create a profile in the caller-owned transaction."""
        self.people.get(campaign, person_id)
        return self._insert_profile(
            person_id,
            short_bio=short_bio,
            appearance=appearance,
            image_path=image_path,
        )

    def _insert_profile(
        self,
        person_id: int,
        *,
        short_bio: str = "",
        appearance: str = "",
        image_path: str = "",
    ) -> CharacterProfile:
        """Insert a profile after its person has already been validated."""
        if self.db.get(CharacterProfile, person_id) is not None:
            raise HTTPException(
                status_code=409,
                detail="This person already has a character profile",
            )

        profile = CharacterProfile(
            person_id=person_id,
            short_bio=short_bio.strip(),
            appearance=appearance.strip(),
            image_path=image_path,
        )
        self.db.add(profile)
        self.db.flush()
        return profile

    def stage_create(
        self,
        campaign: Campaign,
        character: CharacterCreate,
    ) -> CharacterProfile:
        """Create the person/profile aggregate in the caller-owned transaction."""
        has_person_id = character.person_id is not None
        has_person_data = character.person is not None
        if has_person_id == has_person_data:
            raise HTTPException(
                status_code=422,
                detail="Provide either person_id or person, but not both",
            )

        if character.person_id is not None:
            person = self.people.get(campaign, character.person_id)
        else:
            person = self.people.stage_create(campaign, character.person)

        profile = self._insert_profile(
            person.id,
            short_bio=character.short_bio,
            appearance=character.appearance,
        )
        if character.make_active:
            self.set_active_pointer(campaign, profile.person_id)
            self.inventory.stage_sync_default_owner(campaign)
        return profile

    def stage_update(
        self,
        campaign: Campaign,
        person_id: int,
        updated_character: CharacterUpdate,
    ) -> CharacterProfile:
        """Update the person/profile aggregate in the caller-owned transaction."""
        profile = self.get_profile(campaign, person_id)
        self.people.stage_update(
            campaign,
            person_id,
            updated_character.person,
        )
        profile.short_bio = updated_character.short_bio.strip()
        profile.appearance = updated_character.appearance.strip()
        self.db.add(profile)
        self.db.flush()
        return profile

    def set_active_pointer(
        self,
        campaign: Campaign,
        person_id: int,
    ) -> CharacterProfile:
        """Set and flush the active profile without synchronizing inventory."""
        profile = self.get_profile(campaign, person_id)
        campaign.active_character_person_id = person_id
        self.db.add(campaign)
        self.db.flush()
        return profile

    def create(
        self,
        campaign: Campaign,
        character: CharacterCreate,
    ) -> CharacterRead:
        try:
            profile = self.stage_create(campaign, character)
            self.db.commit()
            self.db.refresh(profile)
            self.db.refresh(campaign)
            return self.to_read(profile, campaign)
        except Exception:
            self.db.rollback()
            raise

    def update(
        self,
        campaign: Campaign,
        person_id: int,
        updated_character: CharacterUpdate,
    ) -> CharacterRead:
        try:
            profile = self.stage_update(
                campaign,
                person_id,
                updated_character,
            )
            self.db.commit()
            self.db.refresh(profile)
            return self.to_read(profile, campaign)
        except Exception:
            self.db.rollback()
            raise

    def activate(
        self,
        campaign: Campaign,
        person_id: int,
    ) -> CharacterRead:
        try:
            profile = self.set_active_pointer(campaign, person_id)
            self.inventory.stage_sync_default_owner(campaign)
            self.db.commit()
            self.db.refresh(campaign)
            return self.to_read(profile, campaign)
        except Exception:
            self.db.rollback()
            raise

    def delete(self, campaign: Campaign, person_id: int) -> None:
        profile = self.get_profile(campaign, person_id)
        portrait_path = profile.image_path

        try:
            for note_model, resource_type in (
                (CharacterNote, ResourceType.CHARACTER_NOTE),
                (BackstoryNote, ResourceType.BACKSTORY_NOTE),
            ):
                notes = self.db.exec(
                    select(note_model).where(
                        note_model.character_person_id == person_id
                    )
                ).all()
                for note in notes:
                    handle_tags_of_deleted_resource(
                        self.db,
                        resource_type,
                        note.id,
                    )

            if campaign.active_character_person_id == person_id:
                campaign.active_character_person_id = None
                self.db.add(campaign)

            self.db.delete(profile)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if portrait_path:
            delete_uploaded_file(portrait_path)
