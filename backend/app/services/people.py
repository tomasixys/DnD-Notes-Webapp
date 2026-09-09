from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.authorization.enums import CampaignCapability
from app.authorization.models import CampaignMembership
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
from app.authorization.context import CampaignContext
from app.services.character_notes import (
    BackstoryNoteService,
    CharacterNoteService,
)
from app.services.inventory import InventoryService
from app.services.tags import TagService
from app.concurrency import claim_revision
from app.services.campaign_changes import CampaignChangeService


class PersonService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db
        self.tags = TagService(context)
        self.changes = CampaignChangeService(context)

    def to_read(self, person: Person) -> PersonRead:
        self.context.require(CampaignCapability.SHARED_RESOURCE_READ)
        character_profile = self.db.get(CharacterProfile, person.id)
        return PersonRead(
            revision=person.revision,
            updated_at=person.updated_at,
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
                self.context.active_character_person_id == person.id
            ),
        )

    def get(self, person_id: int) -> Person:
        self.context.require(CampaignCapability.SHARED_RESOURCE_READ)
        person = self.db.get(Person, person_id)
        if (
            person is None
            or person.campaign_id != self.context.campaign_id
        ):
            raise HTTPException(status_code=404, detail="Person not found")

        return person

    def list(self) -> list[Person]:
        self.context.require(CampaignCapability.SHARED_RESOURCE_READ)
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
        self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
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
        self.changes.stage_record(
            ResourceType.PERSON.value,
            db_person.id,
            action="created",
            revision=db_person.revision,
        )
        return db_person

    def stage_update(
        self,
        person_id: int,
        updated_person: PersonData,
        expected_revision: int | None = None,
    ) -> Person:
        """Update a person in the caller-owned transaction."""
        person = self.get(person_id)
        if self.db.get(CharacterProfile, person_id) is not None:
            self.context.require_character_write(person_id)
        else:
            self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        claim_revision(
            self.db,
            person,
            expected_revision or person.revision,
            resource_type=ResourceType.PERSON.value,
        )
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
        self.changes.stage_record(
            ResourceType.PERSON.value,
            person.id,
            action="updated",
            revision=person.revision,
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
        expected_revision: int | None = None,
    ) -> PersonRead:
        """Update and commit a person as a standalone operation."""
        try:
            person = self.stage_update(
                person_id,
                updated_person,
                expected_revision,
            )
            self.db.commit()
            self.db.refresh(person)
            return self.to_read(person)
        except Exception:
            self.db.rollback()
            raise

    def delete(
        self,
        person_id: int,
        expected_revision: int | None = None,
    ) -> DeleteResponse:
        person = self.get(person_id)
        profile = self.db.get(CharacterProfile, person.id)
        if profile is not None:
            self.context.require_character_write(person_id)
        else:
            self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        claim_revision(
            self.db,
            person,
            expected_revision or person.revision,
            resource_type=ResourceType.PERSON.value,
        )
        portrait_path = profile.image_path if profile is not None else ""

        try:
            if profile is not None:
                CharacterNoteService(
                    self.context,
                ).stage_delete_all_for_character(person.id)
                BackstoryNoteService(
                    self.context,
                ).stage_delete_all_for_character(person.id)

            memberships = self.db.exec(
                select(CampaignMembership).where(
                    CampaignMembership.campaign_id
                    == self.context.campaign_id,
                    (
                        (
                            CampaignMembership.assigned_character_person_id
                            == person.id
                        )
                        | (
                            CampaignMembership.active_character_person_id
                            == person.id
                        )
                    ),
                )
            ).all()
            for membership in memberships:
                if (
                    membership.active_character_person_id == person.id
                ):
                    membership.active_character_person_id = None
                if (
                    membership.assigned_character_person_id == person.id
                ):
                    membership.assigned_character_person_id = None
                self.db.add(membership)

            InventoryService(self.context).stage_sync_default_owner()
            self.tags.stage_handle_resource_deletion(
                ResourceType.PERSON,
                person.id,
            )
            self.changes.stage_record(
                ResourceType.PERSON.value,
                person.id,
                action="deleted",
                revision=person.revision,
            )
            self.db.delete(person)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if portrait_path:
            delete_uploaded_file(portrait_path)
        return DeleteResponse(deleted_id=person_id)
