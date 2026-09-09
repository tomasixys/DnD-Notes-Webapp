from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol

from fastapi import HTTPException
from sqlmodel import select

from app.models.api import (
    BackstoryNoteRead,
    CampaignBackupCharacterNote,
    CharacterNoteData,
    CharacterNoteGrantData,
    CharacterNoteGrantRead,
    CharacterNoteRead,
    DeleteResponse,
)
from app.auth.enums import UserStatus
from app.auth.models import User
from app.authorization.enums import (
    ResourceGrantPermission,
    ResourceVisibility,
)
from app.authorization.models import (
    BackstoryNoteGrant,
    CampaignMembership,
    CharacterNoteGrant,
)
from app.authorization.resource_policy import ResourceAccessPolicy
from app.models.database import (
    BackstoryNote,
    CharacterNote,
    CharacterProfile,
)
from app.models.enums import ResourceType
from app.authorization.context import CampaignContext
from app.services.tags import TagService
from app.concurrency import claim_revision
from app.services.campaign_changes import CampaignChangeService


PersonalNote = CharacterNote | BackstoryNote
PersonalNoteRead = CharacterNoteRead | BackstoryNoteRead


@dataclass(frozen=True)
class _NoteDefinition:
    model: type[CharacterNote] | type[BackstoryNote]
    grant_model: type[CharacterNoteGrant] | type[BackstoryNoteGrant]
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
        self.tags = TagService(context)
        self.policy = ResourceAccessPolicy(context)
        self.changes = CampaignChangeService(context)

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
        grants = self._grant_reads(note)
        return self.definition.read_model(
            revision=note.revision,
            id=note.id,
            campaign_id=note.campaign_id,
            character_person_id=note.character_person_id,
            title=note.title,
            content=note.content,
            visibility=note.visibility,
            created_by_user_id=note.created_by_user_id,
            access_owner_user_id=note.access_owner_user_id,
            grants=grants,
            can_write=self.policy.can_write(
                note,
                self.definition.grant_model,
            ),
            can_manage_access=self.policy.can_manage_access(note),
            created_at=note.created_at,
            updated_at=note.updated_at,
            tags=self.tags.list_tag_reads(
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
        self.policy.require_read(
            note,
            self.definition.grant_model,
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
                self.policy.readable_clause(
                    model,
                    self.definition.grant_model,
                ),
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
        visibility: ResourceVisibility,
        grants: list[CharacterNoteGrantData],
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
            "created_by_user_id": (
                self.context.user.id if normalize_text else None
            ),
            "visibility": visibility,
            "access_owner_user_id": self.context.user.id,
        }
        if created_at is not None:
            values["created_at"] = created_at
        if updated_at is not None:
            values["updated_at"] = updated_at

        note = self.definition.model(**values)
        self.db.add(note)
        self.db.flush()
        self._stage_sync_grants(note, grants)
        self.tags.stage_sync_tags(
            self.definition.resource_type,
            note.id,
            tags,
        )
        self.tags.stage_refresh_references(
            self.definition.resource_type,
            note.id,
        )
        self.changes.stage_record(
            self.definition.resource_type.value,
            note.id,
            action="created",
            revision=note.revision,
            recipient_user_ids=self._recipient_user_ids(note),
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
            visibility=note_data.visibility,
            grants=note_data.grants,
        )

    def stage_restore(
        self,
        person_id: int,
        note_backup: CampaignBackupCharacterNote,
    ) -> PersonalNote:
        restored_visibility = (
            ResourceVisibility.CAMPAIGN
            if note_backup.visibility is ResourceVisibility.CAMPAIGN
            else ResourceVisibility.PRIVATE
        )
        return self._stage_insert(
            person_id,
            title=note_backup.title,
            content=note_backup.content,
            tags=note_backup.tags,
            visibility=restored_visibility,
            grants=[],
            created_at=note_backup.created_at,
            updated_at=note_backup.updated_at,
            normalize_text=False,
        )

    def stage_update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
        expected_revision: int | None = None,
    ) -> PersonalNote:
        note = self.get(person_id, note_id)
        self.policy.require_write(
            note,
            self.definition.grant_model,
            detail=self.definition.not_found_detail,
        )
        previous_recipients = self._recipient_user_ids(note)
        claim_revision(
            self.db,
            note,
            expected_revision or note.revision,
            resource_type=self.definition.resource_type.value,
        )
        requested_grants = self._normalized_grant_data(
            note_data.visibility,
            note_data.grants,
            access_owner_user_id=(
                note.access_owner_user_id or self.context.user.id
            ),
        )
        current_grants = {
            (grant.user_id, grant.permission)
            for grant in self._grant_rows(note.id)
        }
        access_changed = (
            note_data.visibility is not note.visibility
            or current_grants != set(requested_grants)
        )
        if access_changed and not self.policy.can_manage_access(note):
            raise HTTPException(
                status_code=403,
                detail="Resource access ownership is required",
            )
        previous_title = note.title
        note.title = self._normalize_title(note_data.title)
        note.content = note_data.content.strip()
        if (
            note_data.visibility is not ResourceVisibility.CAMPAIGN
            and note.access_owner_user_id is None
        ):
            note.access_owner_user_id = self.context.user.id
        note.visibility = note_data.visibility
        self.db.add(note)
        self.db.flush()
        self._stage_sync_grants(
            note,
            note_data.grants,
            normalized=requested_grants,
        )
        self.tags.stage_sync_tags(
            self.definition.resource_type,
            note.id,
            note_data.tags,
        )
        self.tags.stage_refresh_references(
            self.definition.resource_type,
            note.id,
            previous_labels=[previous_title],
        )
        self.changes.stage_record(
            self.definition.resource_type.value,
            note.id,
            action="updated",
            revision=note.revision,
            recipient_user_ids=(
                previous_recipients
                | self._recipient_user_ids(note)
            ),
        )
        return note

    def stage_delete(
        self,
        person_id: int,
        note_id: int,
        expected_revision: int | None = None,
    ) -> None:
        note = self.get(person_id, note_id)
        self.policy.require_write(
            note,
            self.definition.grant_model,
            detail=self.definition.not_found_detail,
        )
        recipients = self._recipient_user_ids(note)
        claim_revision(
            self.db,
            note,
            expected_revision or note.revision,
            resource_type=self.definition.resource_type.value,
        )
        self.tags.stage_handle_resource_deletion(
            self.definition.resource_type,
            note.id,
        )
        self.changes.stage_record(
            self.definition.resource_type.value,
            note.id,
            action="deleted",
            revision=note.revision,
            recipient_user_ids=recipients,
        )
        self.db.delete(note)
        self.db.flush()

    def stage_delete_all_for_character(
        self,
        person_id: int,
    ) -> None:
        self.context.require_character_write(person_id)
        model = self.definition.model
        notes = self.db.exec(
            select(model).where(
                model.campaign_id == self.context.campaign_id,
                model.character_person_id == person_id,
            )
        ).all()
        for note in notes:
            self.policy.require_write(
                note,
                self.definition.grant_model,
                detail=self.definition.not_found_detail,
            )
            recipients = self._recipient_user_ids(note)
            claim_revision(
                self.db,
                note,
                note.revision,
                resource_type=self.definition.resource_type.value,
            )
            self.tags.stage_handle_resource_deletion(
                self.definition.resource_type,
                note.id,
            )
            self.changes.stage_record(
                self.definition.resource_type.value,
                note.id,
                action="deleted",
                revision=note.revision,
                recipient_user_ids=recipients,
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
        expected_revision: int | None = None,
    ) -> PersonalNoteRead:
        return self._commit_note(
            lambda: self.stage_update(
                person_id,
                note_id,
                note_data,
                expected_revision,
            )
        )

    def delete(
        self,
        person_id: int,
        note_id: int,
        expected_revision: int | None = None,
    ) -> DeleteResponse:
        try:
            self.stage_delete(
                person_id,
                note_id,
                expected_revision,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return DeleteResponse(deleted_id=note_id)

    def to_backup(
        self,
        note: PersonalNote,
    ) -> CampaignBackupCharacterNote:
        return CampaignBackupCharacterNote(
            title=note.title,
            content=note.content,
            tags=self.tags.list_values(
                self.definition.resource_type,
                note.id,
            ),
            created_at=note.created_at,
            updated_at=note.updated_at,
            visibility=note.visibility,
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
                self.policy.readable_clause(
                    model,
                    self.definition.grant_model,
                ),
            )
            .order_by(model.created_at, model.id)
        ).all()
        return [self.to_backup(note) for note in notes]

    def _grant_rows(self, note_id: int):
        model = self.definition.grant_model
        return self.db.exec(
            select(model)
            .where(model.note_id == note_id)
            .order_by(model.user_id)
        ).all()

    def _recipient_user_ids(self, note: PersonalNote) -> set[int]:
        if note.visibility is ResourceVisibility.CAMPAIGN:
            return set(
                self.db.exec(
                    select(CampaignMembership.user_id).where(
                        CampaignMembership.campaign_id
                        == self.context.campaign_id,
                        CampaignMembership.is_custodial.is_(False),
                    )
                ).all()
            )
        recipients = (
            {note.access_owner_user_id}
            if note.access_owner_user_id is not None
            else set()
        )
        if note.visibility is ResourceVisibility.RESTRICTED:
            recipients.update(
                grant.user_id
                for grant in self._grant_rows(note.id)
            )
        return recipients

    def _grant_reads(
        self,
        note: PersonalNote,
    ) -> list[CharacterNoteGrantRead]:
        model = self.definition.grant_model
        rows = self.db.exec(
            select(model, User)
            .join(User, User.id == model.user_id)
            .join(
                CampaignMembership,
                (CampaignMembership.user_id == model.user_id)
                & (
                    CampaignMembership.campaign_id
                    == self.context.campaign_id
                ),
            )
            .where(
                model.note_id == note.id,
                CampaignMembership.is_custodial.is_(False),
                User.status == UserStatus.ACTIVE,
                User.can_login.is_(True),
            )
            .order_by(User.normalized_username, User.id)
        ).all()
        return [
            CharacterNoteGrantRead(
                user_id=grant.user_id,
                username=user.username,
                display_name=user.display_name,
                permission=grant.permission,
            )
            for grant, user in rows
        ]

    def _normalized_grant_data(
        self,
        visibility: ResourceVisibility,
        grants: list[CharacterNoteGrantData],
        *,
        access_owner_user_id: int,
    ) -> list[tuple[int, ResourceGrantPermission]]:
        if visibility is not ResourceVisibility.RESTRICTED:
            if grants:
                raise HTTPException(
                    status_code=422,
                    detail="Only restricted resources can have grants",
                )
            return []

        normalized: dict[int, ResourceGrantPermission] = {}
        for grant in grants:
            if grant.user_id == access_owner_user_id:
                raise HTTPException(
                    status_code=422,
                    detail="The access owner does not need a grant",
                )
            if grant.user_id in normalized:
                raise HTTPException(
                    status_code=422,
                    detail="A user can have only one resource grant",
                )
            membership = self.db.exec(
                select(CampaignMembership, User)
                .join(User, User.id == CampaignMembership.user_id)
                .where(
                    CampaignMembership.campaign_id
                    == self.context.campaign_id,
                    CampaignMembership.user_id == grant.user_id,
                    CampaignMembership.is_custodial.is_(False),
                    User.status == UserStatus.ACTIVE,
                    User.can_login.is_(True),
                )
            ).first()
            if membership is None:
                raise HTTPException(
                    status_code=422,
                    detail="Resource grants require an active campaign member",
                )
            normalized[grant.user_id] = grant.permission
        return sorted(normalized.items())

    def _stage_sync_grants(
        self,
        note: PersonalNote,
        grants: list[CharacterNoteGrantData],
        *,
        normalized: list[
            tuple[int, ResourceGrantPermission]
        ] | None = None,
    ) -> None:
        normalized = normalized or self._normalized_grant_data(
            note.visibility,
            grants,
            access_owner_user_id=note.access_owner_user_id,
        )
        for grant in self._grant_rows(note.id):
            self.db.delete(grant)
        self.db.flush()
        for user_id, permission in normalized:
            self.db.add(
                self.definition.grant_model(
                    note_id=note.id,
                    user_id=user_id,
                    permission=permission,
                )
            )
        self.db.flush()


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
                grant_model=CharacterNoteGrant,
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
        expected_revision: int | None = None,
    ) -> CharacterNote:
        return self._operations.stage_update(
            person_id,
            note_id,
            note_data,
            expected_revision,
        )

    def update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
        expected_revision: int | None = None,
    ) -> CharacterNoteRead:
        return self._operations.update(
            person_id,
            note_id,
            note_data,
            expected_revision,
        )

    def stage_delete(
        self,
        person_id: int,
        note_id: int,
        expected_revision: int | None = None,
    ) -> None:
        self._operations.stage_delete(
            person_id,
            note_id,
            expected_revision,
        )

    def delete(
        self,
        person_id: int,
        note_id: int,
        expected_revision: int | None = None,
    ) -> DeleteResponse:
        return self._operations.delete(
            person_id,
            note_id,
            expected_revision,
        )

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
                grant_model=BackstoryNoteGrant,
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
        expected_revision: int | None = None,
    ) -> BackstoryNote:
        return self._operations.stage_update(
            person_id,
            note_id,
            note_data,
            expected_revision,
        )

    def update(
        self,
        person_id: int,
        note_id: int,
        note_data: CharacterNoteData,
        expected_revision: int | None = None,
    ) -> BackstoryNoteRead:
        return self._operations.update(
            person_id,
            note_id,
            note_data,
            expected_revision,
        )

    def stage_delete(
        self,
        person_id: int,
        note_id: int,
        expected_revision: int | None = None,
    ) -> None:
        self._operations.stage_delete(
            person_id,
            note_id,
            expected_revision,
        )

    def delete(
        self,
        person_id: int,
        note_id: int,
        expected_revision: int | None = None,
    ) -> DeleteResponse:
        return self._operations.delete(
            person_id,
            note_id,
            expected_revision,
        )

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
