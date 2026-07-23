from fastapi import HTTPException
from sqlmodel import Session, select

from app.file_storage import delete_uploaded_file
from app.models.api import PersonData, PersonRead
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
from app.tags import (
    get_resource_relationship,
    get_resource_tag_reads,
    handle_tags_of_deleted_resource,
    refresh_reference_tags_for_resource,
    sync_resource_relationship,
    sync_resource_tags,
)


class PersonService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    def to_read(self, person: Person) -> PersonRead:
        character_profile = self.db.get(CharacterProfile, person.id)
        return PersonRead(
            id=person.id,
            campaign_id=person.campaign_id,
            name=person.name,
            role=person.role,
            faction=get_resource_relationship(
                self.db,
                ResourceType.PERSON,
                person.id,
                RelationshipType.MEMBER_OF,
            ),
            location=get_resource_relationship(
                self.db,
                ResourceType.PERSON,
                person.id,
                RelationshipType.LOCATED_IN,
            ),
            description=person.description,
            tags=get_resource_tag_reads(
                self.db,
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
            .order_by(Person.name)
        )
        return self.db.exec(statement).all()

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
        sync_resource_tags(
            self.db,
            self.context.campaign_id,
            ResourceType.PERSON,
            db_person.id,
            person.tags,
        )
        sync_resource_relationship(
            self.db,
            self.context.campaign_id,
            ResourceType.PERSON,
            db_person.id,
            RelationshipType.MEMBER_OF,
            ResourceType.FACTION,
            person.faction,
        )
        sync_resource_relationship(
            self.db,
            self.context.campaign_id,
            ResourceType.PERSON,
            db_person.id,
            RelationshipType.LOCATED_IN,
            ResourceType.LOCATION,
            person.location,
        )
        refresh_reference_tags_for_resource(
            self.db,
            self.context.campaign_id,
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
        sync_resource_tags(
            self.db,
            person.campaign_id,
            ResourceType.PERSON,
            person.id,
            updated_person.tags,
        )
        sync_resource_relationship(
            self.db,
            person.campaign_id,
            ResourceType.PERSON,
            person.id,
            RelationshipType.MEMBER_OF,
            ResourceType.FACTION,
            updated_person.faction,
        )
        sync_resource_relationship(
            self.db,
            person.campaign_id,
            ResourceType.PERSON,
            person.id,
            RelationshipType.LOCATED_IN,
            ResourceType.LOCATION,
            updated_person.location,
        )
        refresh_reference_tags_for_resource(
            self.db,
            person.campaign_id,
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

    def delete(self, person_id: int) -> None:
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

            handle_tags_of_deleted_resource(
                self.db,
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
