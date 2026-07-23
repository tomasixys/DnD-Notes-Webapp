from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.file_storage import delete_uploaded_file
from app.models.api import (
    CampaignBackupPerson,
    DeleteResponse,
    PersonData,
    PersonRead,
)
from app.models.database import (
    CharacterProfile,
    Person,
)
from app.models.enums import RelationshipType, ResourceType
from app.services.campaign_context import CampaignContext
from app.services.character_notes import (
    BackstoryNoteService,
    CharacterNoteService,
)
from app.services.tags import TagService


class PersonService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db
        self.tags = TagService(context)

    def to_read(self, person: Person) -> PersonRead:
        character_profile = self.db.get(CharacterProfile, person.id)
        return PersonRead(
            id=person.id,
            campaign_id=person.campaign_id,
            name=person.name,
            role=person.role,
            faction=self.tags.get_relationship(
                ResourceType.PERSON,
                person.id,
                RelationshipType.MEMBER_OF,
            ),
            location=self.tags.get_relationship(
                ResourceType.PERSON,
                person.id,
                RelationshipType.LOCATED_IN,
            ),
            description=person.description,
            tags=self.tags.list_tag_reads(
                ResourceType.PERSON,
                person.id,
            ),
            character_profile_available=character_profile is not None,
            is_active_character=(
                self.context.campaign.active_character_person_id == person.id
            ),
        )

    def get(self, person_id: int) -> Person:
        person = self.db.get(Person, person_id)
        if (
            person is None
            or person.campaign_id != self.context.campaign_id
        ):
            raise HTTPException(status_code=404, detail="Person not found")

        return person

    def list(self) -> list[Person]:
        statement = (
            select(Person)
            .where(Person.campaign_id == self.context.campaign_id)
            .order_by(func.lower(Person.name), Person.id)
        )
        return self.db.exec(statement).all()

    def to_backup(self, person: Person) -> CampaignBackupPerson:
        faction = self.tags.get_relationship(
            ResourceType.PERSON,
            person.id,
            RelationshipType.MEMBER_OF,
        )
        location = self.tags.get_relationship(
            ResourceType.PERSON,
            person.id,
            RelationshipType.LOCATED_IN,
        )
        return CampaignBackupPerson(
            backup_id=person.id,
            name=person.name,
            role=person.role,
            faction=faction.label if faction else "",
            location=location.label if location else "",
            description=person.description,
            tags=self.tags.list_values(
                ResourceType.PERSON,
                person.id,
            ),
        )

    def list_backup_entries(self) -> list[CampaignBackupPerson]:
        people = sorted(
            self.list(),
            key=lambda person: (person.name.lower(), person.id or 0),
        )
        return [self.to_backup(person) for person in people]

    def stage_create(self, person: PersonData) -> Person:
        """Create and synchronize a person in the caller-owned transaction."""
        db_person = Person(
            campaign_id=self.context.campaign_id,
            name=person.name.strip(),
            role=person.role.strip(),
            description=person.description.strip(),
        )
        if not db_person.name:
            raise HTTPException(
                status_code=422,
                detail="Person name cannot be blank",
            )

        self.db.add(db_person)
        self.db.flush()
        self.tags.stage_sync_tags(
            ResourceType.PERSON,
            db_person.id,
            person.tags,
        )
        self.tags.stage_sync_relationship(
            ResourceType.PERSON,
            db_person.id,
            RelationshipType.MEMBER_OF,
            ResourceType.FACTION,
            person.faction,
        )
        self.tags.stage_sync_relationship(
            ResourceType.PERSON,
            db_person.id,
            RelationshipType.LOCATED_IN,
            ResourceType.LOCATION,
            person.location,
        )
        self.tags.stage_refresh_references(
            ResourceType.PERSON,
            db_person.id,
        )
        return db_person

    def stage_update(
        self,
        person_id: int,
        updated_person: PersonData,
    ) -> Person:
        """Update a person in the caller-owned transaction."""
        person = self.get(person_id)
        previous_name = person.name
        person.name = updated_person.name.strip()
        person.role = updated_person.role.strip()
        person.description = updated_person.description.strip()
        if not person.name:
            raise HTTPException(
                status_code=422,
                detail="Person name cannot be blank",
            )

        self.db.add(person)
        self.db.flush()
        self.tags.stage_sync_tags(
            ResourceType.PERSON,
            person.id,
            updated_person.tags,
        )
        self.tags.stage_sync_relationship(
            ResourceType.PERSON,
            person.id,
            RelationshipType.MEMBER_OF,
            ResourceType.FACTION,
            updated_person.faction,
        )
        self.tags.stage_sync_relationship(
            ResourceType.PERSON,
            person.id,
            RelationshipType.LOCATED_IN,
            ResourceType.LOCATION,
            updated_person.location,
        )
        self.tags.stage_refresh_references(
            ResourceType.PERSON,
            person.id,
            previous_labels=[previous_name],
        )
        return person

    def create(
        self,
        person: PersonData,
    ) -> PersonRead:
        """Create and commit a person as a standalone operation."""
        try:
            db_person = self.stage_create(person)
            self.db.commit()
            self.db.refresh(db_person)
            return self.to_read(db_person)
        except Exception:
            self.db.rollback()
            raise

    def update(
        self,
        person_id: int,
        updated_person: PersonData,
    ) -> PersonRead:
        """Update and commit a person as a standalone operation."""
        try:
            person = self.stage_update(
                person_id,
                updated_person,
            )
            self.db.commit()
            self.db.refresh(person)
            return self.to_read(person)
        except Exception:
            self.db.rollback()
            raise

    def delete(self, person_id: int) -> DeleteResponse:
        person = self.get(person_id)
        profile = self.db.get(CharacterProfile, person.id)
        portrait_path = profile.image_path if profile is not None else ""

        try:
            if profile is not None:
                CharacterNoteService(
                    self.context,
                ).stage_delete_all_for_character(person.id)
                BackstoryNoteService(
                    self.context,
                ).stage_delete_all_for_character(person.id)

            if self.context.campaign.active_character_person_id == person.id:
                self.context.campaign.active_character_person_id = None
                self.db.add(self.context.campaign)

            self.tags.stage_handle_resource_deletion(
                ResourceType.PERSON,
                person.id,
            )
            self.db.delete(person)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if portrait_path:
            delete_uploaded_file(portrait_path)
        return DeleteResponse(deleted_id=person_id)
