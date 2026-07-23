from fastapi import HTTPException, UploadFile
from sqlmodel import select

from app.file_storage import (
    build_upload_url,
    delete_uploaded_file,
    save_image_from_uploadfile,
)
from app.models.api import (
    CampaignBackupCharacter,
    CharacterDeleteResponse,
    CharacterCreate,
    CharacterRead,
    CharacterUpdate,
)
from app.models.database import (
    CharacterProfile,
    Person,
)
from app.services.campaign_context import CampaignContext
from app.services.character_notes import (
    BackstoryNoteService,
    CharacterNoteService,
)
from app.services.inventory import InventoryService
from app.services.people import PersonService


class CharacterService:
    def __init__(
        self,
        context: CampaignContext,
        people: PersonService | None = None,
        inventory: InventoryService | None = None,
    ):
        self.context = context
        self.db = context.db
        self.people = people or PersonService(context)
        self.inventory = inventory or InventoryService(context)

    def to_read(
        self,
        profile: CharacterProfile,
    ) -> CharacterRead:
        person = self.people.get(profile.person_id)
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
                self.context.campaign.active_character_person_id
                == profile.person_id
            ),
        )

    def get_profile(
        self,
        person_id: int,
    ) -> CharacterProfile:
        self.people.get(person_id)
        profile = self.db.get(CharacterProfile, person_id)
        if profile is None:
            raise HTTPException(
                status_code=404,
                detail="Character profile not found",
            )
        return profile

    def get_active(self) -> CharacterRead | None:
        campaign = self.context.campaign
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

        return self.to_read(profile)

    def list_profiles_for_backup(self) -> list[CharacterProfile]:
        return self.db.exec(
            select(CharacterProfile)
            .join(Person, Person.id == CharacterProfile.person_id)
            .where(Person.campaign_id == self.context.campaign_id)
            .order_by(Person.name, Person.id)
        ).all()

    def list_backup_entries(
        self,
        image_archive_paths: dict[int, str],
    ) -> list[CampaignBackupCharacter]:
        character_notes = CharacterNoteService(self.context, self)
        backstory_notes = BackstoryNoteService(self.context, self)
        return [
            CampaignBackupCharacter(
                person_backup_id=profile.person_id,
                short_bio=profile.short_bio,
                appearance=profile.appearance,
                image_archive_path=image_archive_paths.get(
                    profile.person_id,
                    "",
                ),
                notes=character_notes.list_backup_entries(
                    profile.person_id
                ),
                backstory_notes=backstory_notes.list_backup_entries(
                    profile.person_id
                ),
            )
            for profile in self.list_profiles_for_backup()
        ]

    def stage_create_profile(
        self,
        person_id: int,
        *,
        short_bio: str = "",
        appearance: str = "",
        image_path: str = "",
    ) -> CharacterProfile:
        """Create a profile in the caller-owned transaction."""
        self.people.get(person_id)
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
            person = self.people.get(character.person_id)
        else:
            person = self.people.stage_create(character.person)

        profile = self._insert_profile(
            person.id,
            short_bio=character.short_bio,
            appearance=character.appearance,
        )
        if character.make_active:
            self.set_active_pointer(profile.person_id)
            self.inventory.stage_sync_default_owner()
        return profile

    def stage_update(
        self,
        person_id: int,
        updated_character: CharacterUpdate,
    ) -> CharacterProfile:
        """Update the person/profile aggregate in the caller-owned transaction."""
        profile = self.get_profile(person_id)
        self.people.stage_update(
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
        person_id: int,
    ) -> CharacterProfile:
        """Set and flush the active profile without synchronizing inventory."""
        profile = self.get_profile(person_id)
        self.context.campaign.active_character_person_id = person_id
        self.db.add(self.context.campaign)
        self.db.flush()
        return profile

    def create(
        self,
        character: CharacterCreate,
    ) -> CharacterRead:
        try:
            profile = self.stage_create(character)
            self.db.commit()
            self.db.refresh(profile)
            self.db.refresh(self.context.campaign)
            return self.to_read(profile)
        except Exception:
            self.db.rollback()
            raise

    def update(
        self,
        person_id: int,
        updated_character: CharacterUpdate,
    ) -> CharacterRead:
        try:
            profile = self.stage_update(
                person_id,
                updated_character,
            )
            self.db.commit()
            self.db.refresh(profile)
            return self.to_read(profile)
        except Exception:
            self.db.rollback()
            raise

    def activate(
        self,
        person_id: int,
    ) -> CharacterRead:
        try:
            profile = self.set_active_pointer(person_id)
            self.inventory.stage_sync_default_owner()
            self.db.commit()
            self.db.refresh(self.context.campaign)
            return self.to_read(profile)
        except Exception:
            self.db.rollback()
            raise

    def replace_portrait(
        self,
        person_id: int,
        image: UploadFile,
    ) -> CharacterRead:
        profile = self.get_profile(person_id)
        old_portrait_path = profile.image_path
        saved_portrait_path: str | None = None

        try:
            saved_portrait_path = save_image_from_uploadfile(
                self.context.campaign_id,
                image,
            )
            profile.image_path = saved_portrait_path
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        except Exception:
            self.db.rollback()
            if saved_portrait_path:
                delete_uploaded_file(saved_portrait_path)
            raise

        if (
            old_portrait_path
            and old_portrait_path != saved_portrait_path
        ):
            delete_uploaded_file(old_portrait_path)
        return self.to_read(profile)

    def remove_portrait(
        self,
        person_id: int,
    ) -> CharacterRead:
        profile = self.get_profile(person_id)
        old_portrait_path = profile.image_path

        try:
            profile.image_path = ""
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        except Exception:
            self.db.rollback()
            raise

        if old_portrait_path:
            delete_uploaded_file(old_portrait_path)
        return self.to_read(profile)

    def delete(self, person_id: int) -> CharacterDeleteResponse:
        profile = self.get_profile(person_id)
        portrait_path = profile.image_path

        try:
            CharacterNoteService(
                self.context,
                self,
            ).stage_delete_all_for_character(person_id)
            BackstoryNoteService(
                self.context,
                self,
            ).stage_delete_all_for_character(person_id)

            if self.context.campaign.active_character_person_id == person_id:
                self.context.campaign.active_character_person_id = None
                self.db.add(self.context.campaign)

            self.db.delete(profile)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if portrait_path:
            delete_uploaded_file(portrait_path)
        return CharacterDeleteResponse(
            deleted_id=person_id,
            active_character=self.get_active(),
        )
