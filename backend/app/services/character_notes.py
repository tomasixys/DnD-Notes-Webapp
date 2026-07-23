from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from fastapi import HTTPException
from sqlmodel import select

from app.models.api import (
    BackstoryNoteRead,
    CampaignBackupCharacterNote,
    CharacterNoteData,
    CharacterNoteRead,
)
from app.models.database import (
    BackstoryNote,
    CharacterNote,
    CharacterProfile,
)
from app.models.enums import ResourceType
from app.services.campaign_context import CampaignContext
from app.tags import (
    get_resource_tag_reads,
    get_resource_tags,
    handle_tags_of_deleted_resource,
    refresh_reference_tags_for_resource,
    sync_resource_tags,
)


PersonalNote = CharacterNote | BackstoryNote
PersonalNoteRead = CharacterNoteRead | BackstoryNoteRead


@dataclass(frozen=True)
class _NoteDefinition:
    model: type[CharacterNote] | type[BackstoryNote]
    resource_type: ResourceType
    read_model: type[CharacterNoteRead] | type[BackstoryNoteRead]
    not_found_detail: str


class _CharacterProfileResolver(Protocol):
    def get_profile(self, person_id: int) -> CharacterProfile: ...


class _PersonalNoteOperations:
    """Shared implementation behind the two explicit note-domain services."""

    def __init__(
        self,
        context: CampaignContext,
        characters: _CharacterProfileResolver | None,
        definition: _NoteDefinition,
    ):
        self.context = context
        self.db = context.db
        self.characters = characters
        self.definition = definition

    def _verify_character(
        self,
        person_id: int,
    ) -> None:
        if self.characters is None:
            from app.services.characters import CharacterService

            self.characters = CharacterService(self.context)
        self.characters.get_profile(person_id)

    @staticmethod
    def _normalize_title(title: str) -> str:
        normalized = title.strip()
        if not normalized:
            raise HTTPException(
                status_code=422,
                detail="Note title cannot be blank",
            )
        return normalized

    def to_read(self, note: PersonalNote) -> PersonalNoteRead:
        return self.definition.read_model(
            id=note.id,
            campaign_id=note.campaign_id,
            character_person_id=note.character_person_id,
            title=note.title,
            content=note.content,
            created_at=note.created_at,
            updated_at=note.updated_at,
            tags=get_resource_tag_reads(
                self.db,
                self.definition.resource_type,
                note.id,
            ),
        )

    def get(
        self,
        person_id: int,
        note_id: int,
    ) -> PersonalNote:
        self._verify_character(person_id)
        note = self.db.get(self.definition.model, note_id)
        if (
            note is None
            or note.campaign_id != self.context.campaign_id
            or note.character_person_id != person_id
        ):
            raise HTTPException(
                status_code=404,
                detail=self.definition.not_found_detail,
            )
        return note

    def list_for_character(
        self,
        person_id: int,
    ) -> list[PersonalNoteRead]:
        self._verify_character(person_id)
        model = self.definition.model
        statement = (
            select(model)
            .where(
                model.campaign_id == self.context.campaign_id,
                model.character_person_id == person_id,
            )
            .order_by(model.updated_at.desc(), model.id.desc())
        )
        return [self.to_read(note) for note in self.db.exec(statement).all()]

    def _stage_insert(
        self,
        person_id: int,
        *,
        title: str,
        content: str,
        tags: list[str],
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        normalize_text: bool = True,
    ) -> PersonalNote:
        self._verify_character(person_id)
        values = {
            "campaign_id": self.context.campaign_id,
            "character_person_id": person_id,
            "title": (
                self._normalize_title(title) if normalize_text else title
            ),
            "content": content.strip() if normalize_text else content,
        }
        if created_at is not None:
            values["created_at"] = created_at
        if updated_at is not None:
            values["updated_at"] = updated_at

        note = self.definition.model(**values)
        self.db.add(note)
        self.db.flush()
        sync_resource_tags(
            self.db,
            self.context.campaign_id,
            self.definition.resource_type,
            note.id,
            tags,
        )
        refresh_reference_tags_for_resource(
            self.db,
            self.context.campaign_id,
            self.definition.resource_type,
            note.id,
        )
        return note

    def stage_create(
        self,
        person_id: int,
        note_data: CharacterNoteData,
    ) -> PersonalNote:
        return self._stage_insert(
            person_id,
            title=note_data.title,
            content=note_data.content,
            tags=note_data.tags,
        )

    def stage_restore(
        self,
        person_id: int,
        note_backup: CampaignBackupCharacterNote,
    ) -> PersonalNote:
        return self._stage_insert(
            person_id,
            title=note_backup.title,
            content=note_backup.content,
            tags=note_backup.tags,
            created_at=note_backup.created_at,
            updated_at=note_backup.updated_at,
            normalize_text=False,
        )

    def stage_update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
    ) -> PersonalNote:
        note = self.get(person_id, note_id)
        previous_title = note.title
        note.title = self._normalize_title(note_data.title)
        note.content = note_data.content.strip()
        note.updated_at = datetime.now(timezone.utc)
        self.db.add(note)
        self.db.flush()
        sync_resource_tags(
            self.db,
            self.context.campaign_id,
            self.definition.resource_type,
            note.id,
            note_data.tags,
        )
        refresh_reference_tags_for_resource(
            self.db,
            self.context.campaign_id,
            self.definition.resource_type,
            note.id,
            previous_labels=[previous_title],
        )
        return note

    def stage_delete(
        self,
        person_id: int,
        note_id: int,
    ) -> None:
        note = self.get(person_id, note_id)
        handle_tags_of_deleted_resource(
            self.db,
            self.definition.resource_type,
            note.id,
        )
        self.db.delete(note)
        self.db.flush()

    def stage_delete_all_for_character(
        self,
        person_id: int,
    ) -> None:
        model = self.definition.model
        notes = self.db.exec(
            select(model).where(
                model.campaign_id == self.context.campaign_id,
                model.character_person_id == person_id,
            )
        ).all()
        for note in notes:
            handle_tags_of_deleted_resource(
                self.db,
                self.definition.resource_type,
                note.id,
            )
            self.db.delete(note)
        self.db.flush()

    def _commit_note(
        self,
        operation: Callable[[], PersonalNote],
    ) -> PersonalNoteRead:
        try:
            note = operation()
            self.db.commit()
            self.db.refresh(note)
            return self.to_read(note)
        except Exception:
            self.db.rollback()
            raise

    def create(
        self,
        person_id: int,
        note_data: CharacterNoteData,
    ) -> PersonalNoteRead:
        return self._commit_note(
            lambda: self.stage_create(person_id, note_data)
        )

    def update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
    ) -> PersonalNoteRead:
        return self._commit_note(
            lambda: self.stage_update(
                person_id,
                note_id,
                note_data,
            )
        )

    def delete(
        self,
        person_id: int,
        note_id: int,
    ) -> None:
        try:
            self.stage_delete(person_id, note_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def to_backup(
        self,
        note: PersonalNote,
    ) -> CampaignBackupCharacterNote:
        return CampaignBackupCharacterNote(
            title=note.title,
            content=note.content,
            tags=get_resource_tags(
                self.db,
                self.definition.resource_type,
                note.id,
            ),
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    def list_backup_entries(
        self,
        person_id: int,
    ) -> list[CampaignBackupCharacterNote]:
        self._verify_character(person_id)
        model = self.definition.model
        notes = self.db.exec(
            select(model)
            .where(
                model.campaign_id == self.context.campaign_id,
                model.character_person_id == person_id,
            )
            .order_by(model.created_at, model.id)
        ).all()
        return [self.to_backup(note) for note in notes]


class CharacterNoteService:
    def __init__(
        self,
        context: CampaignContext,
        characters: _CharacterProfileResolver | None = None,
    ):
        self._operations = _PersonalNoteOperations(
            context,
            characters,
            _NoteDefinition(
                model=CharacterNote,
                resource_type=ResourceType.CHARACTER_NOTE,
                read_model=CharacterNoteRead,
                not_found_detail="Character note not found",
            ),
        )

    def to_read(self, note: CharacterNote) -> CharacterNoteRead:
        return self._operations.to_read(note)

    def get(
        self,
        person_id: int,
        note_id: int,
    ) -> CharacterNote:
        return self._operations.get(person_id, note_id)

    def list_for_character(
        self,
        person_id: int,
    ) -> list[CharacterNoteRead]:
        return self._operations.list_for_character(person_id)

    def stage_create(
        self,
        person_id: int,
        note_data: CharacterNoteData,
    ) -> CharacterNote:
        return self._operations.stage_create(person_id, note_data)

    def create(
        self,
        person_id: int,
        note_data: CharacterNoteData,
    ) -> CharacterNoteRead:
        return self._operations.create(person_id, note_data)

    def stage_update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
    ) -> CharacterNote:
        return self._operations.stage_update(
            person_id,
            note_id,
            note_data,
        )

    def update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
    ) -> CharacterNoteRead:
        return self._operations.update(
            person_id,
            note_id,
            note_data,
        )

    def stage_delete(
        self,
        person_id: int,
        note_id: int,
    ) -> None:
        self._operations.stage_delete(person_id, note_id)

    def delete(
        self,
        person_id: int,
        note_id: int,
    ) -> None:
        self._operations.delete(person_id, note_id)

    def stage_delete_all_for_character(
        self,
        person_id: int,
    ) -> None:
        self._operations.stage_delete_all_for_character(person_id)

    def to_backup(
        self,
        note: CharacterNote,
    ) -> CampaignBackupCharacterNote:
        return self._operations.to_backup(note)

    def list_backup_entries(
        self,
        person_id: int,
    ) -> list[CampaignBackupCharacterNote]:
        return self._operations.list_backup_entries(person_id)

    def stage_restore(
        self,
        person_id: int,
        note_backup: CampaignBackupCharacterNote,
    ) -> CharacterNote:
        return self._operations.stage_restore(
            person_id,
            note_backup,
        )


class BackstoryNoteService:
    def __init__(
        self,
        context: CampaignContext,
        characters: _CharacterProfileResolver | None = None,
    ):
        self._operations = _PersonalNoteOperations(
            context,
            characters,
            _NoteDefinition(
                model=BackstoryNote,
                resource_type=ResourceType.BACKSTORY_NOTE,
                read_model=BackstoryNoteRead,
                not_found_detail="Character note not found",
            ),
        )

    def to_read(self, note: BackstoryNote) -> BackstoryNoteRead:
        return self._operations.to_read(note)

    def get(
        self,
        person_id: int,
        note_id: int,
    ) -> BackstoryNote:
        return self._operations.get(person_id, note_id)

    def list_for_character(
        self,
        person_id: int,
    ) -> list[BackstoryNoteRead]:
        return self._operations.list_for_character(person_id)

    def stage_create(
        self,
        person_id: int,
        note_data: CharacterNoteData,
    ) -> BackstoryNote:
        return self._operations.stage_create(person_id, note_data)

    def create(
        self,
        person_id: int,
        note_data: CharacterNoteData,
    ) -> BackstoryNoteRead:
        return self._operations.create(person_id, note_data)

    def stage_update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
    ) -> BackstoryNote:
        return self._operations.stage_update(
            person_id,
            note_id,
            note_data,
        )

    def update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
    ) -> BackstoryNoteRead:
        return self._operations.update(
            person_id,
            note_id,
            note_data,
        )

    def stage_delete(
        self,
        person_id: int,
        note_id: int,
    ) -> None:
        self._operations.stage_delete(person_id, note_id)

    def delete(
        self,
        person_id: int,
        note_id: int,
    ) -> None:
        self._operations.delete(person_id, note_id)

    def stage_delete_all_for_character(
        self,
        person_id: int,
    ) -> None:
        self._operations.stage_delete_all_for_character(person_id)

    def to_backup(
        self,
        note: BackstoryNote,
    ) -> CampaignBackupCharacterNote:
        return self._operations.to_backup(note)

    def list_backup_entries(
        self,
        person_id: int,
    ) -> list[CampaignBackupCharacterNote]:
        return self._operations.list_backup_entries(person_id)

    def stage_restore(
        self,
        person_id: int,
        note_backup: CampaignBackupCharacterNote,
    ) -> BackstoryNote:
        return self._operations.stage_restore(
            person_id,
            note_backup,
        )
