from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import false, or_, true
from sqlmodel import select

from app.authorization.context import CampaignContext
from app.authorization.enums import (
    CampaignCapability,
    ResourceGrantPermission,
    ResourceVisibility,
)
from app.authorization.models import (
    BackstoryNoteGrant,
    CharacterNoteGrant,
)
from app.models.database import BackstoryNote, CharacterNote
from app.models.enums import ResourceType


PROTECTED_NOTE_DEFINITIONS = {
    ResourceType.CHARACTER_NOTE: (CharacterNote, CharacterNoteGrant),
    ResourceType.BACKSTORY_NOTE: (BackstoryNote, BackstoryNoteGrant),
}


class ResourceAccessPolicy:
    """Central policy for resource visibility below campaign membership."""

    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    def readable_clause(self, model: type, grant_model: type):
        if self.context.elevated:
            return true()
        if not self.context.can(CampaignCapability.SHARED_RESOURCE_READ):
            return false()

        user_id = self.context.user.id
        granted = (
            select(grant_model.id)
            .where(
                grant_model.note_id == model.id,
                grant_model.user_id == user_id,
            )
            .exists()
        )
        return or_(
            model.visibility == ResourceVisibility.CAMPAIGN,
            model.access_owner_user_id == user_id,
            (
                (model.visibility == ResourceVisibility.RESTRICTED)
                & granted
            ),
        )

    def can_read(self, note: Any, grant_model: type) -> bool:
        if self.context.elevated:
            return True
        if not self.context.can(CampaignCapability.SHARED_RESOURCE_READ):
            return False
        if note.visibility is ResourceVisibility.CAMPAIGN:
            return True
        if note.access_owner_user_id == self.context.user.id:
            return True
        if note.visibility is not ResourceVisibility.RESTRICTED:
            return False
        return self._grant(note.id, grant_model) is not None

    def require_read(
        self,
        note: Any,
        grant_model: type,
        *,
        detail: str,
    ) -> None:
        if not self.can_read(note, grant_model):
            raise HTTPException(status_code=404, detail=detail)

    def can_write(self, note: Any, grant_model: type) -> bool:
        if self.context.elevated:
            return True
        if not self.context.can_write_character(
            note.character_person_id
        ):
            return False
        if note.visibility is ResourceVisibility.CAMPAIGN:
            return True
        if note.access_owner_user_id == self.context.user.id:
            return True
        if note.visibility is not ResourceVisibility.RESTRICTED:
            return False
        grant = self._grant(note.id, grant_model)
        return (
            grant is not None
            and grant.permission is ResourceGrantPermission.WRITE
        )

    def require_write(
        self,
        note: Any,
        grant_model: type,
        *,
        detail: str,
    ) -> None:
        self.require_read(note, grant_model, detail=detail)
        if not self.can_write(note, grant_model):
            raise HTTPException(
                status_code=403,
                detail="Resource permission denied",
            )

    def can_manage_access(self, note: Any) -> bool:
        if self.context.elevated:
            return True
        if not self.context.can_write_character(
            note.character_person_id
        ):
            return False
        return (
            note.access_owner_user_id == self.context.user.id
            or (
                note.visibility is ResourceVisibility.CAMPAIGN
                and note.access_owner_user_id is None
            )
        )

    def can_read_reference(
        self,
        resource_type: ResourceType,
        resource_id: int,
    ) -> bool:
        definition = PROTECTED_NOTE_DEFINITIONS.get(resource_type)
        if definition is None:
            return True
        model, grant_model = definition
        note = self.db.get(model, resource_id)
        return (
            note is not None
            and note.campaign_id == self.context.campaign_id
            and self.can_read(note, grant_model)
        )

    def filter_readable_ids(
        self,
        resource_type: ResourceType,
        resource_ids: list[int],
    ) -> list[int]:
        definition = PROTECTED_NOTE_DEFINITIONS.get(resource_type)
        if definition is None or not resource_ids:
            return resource_ids
        model, grant_model = definition
        statement = select(model.id).where(
            model.campaign_id == self.context.campaign_id,
            model.id.in_(resource_ids),
            self.readable_clause(model, grant_model),
        )
        return list(self.db.exec(statement).all())

    def _grant(self, note_id: int, grant_model: type):
        return self.db.exec(
            select(grant_model).where(
                grant_model.note_id == note_id,
                grant_model.user_id == self.context.user.id,
            )
        ).first()


def stage_release_personal_note_access(
    db,
    *,
    campaign_id: int,
    user_id: int,
    replacement_owner_user_id: int,
) -> None:
    """Revoke grants and move access ownership before membership removal."""
    for model, grant_model in PROTECTED_NOTE_DEFINITIONS.values():
        owned_notes = db.exec(
            select(model).where(
                model.campaign_id == campaign_id,
                model.access_owner_user_id == user_id,
            )
        ).all()
        for note in owned_notes:
            note.access_owner_user_id = replacement_owner_user_id
            db.add(note)

        user_grants = db.exec(
            select(grant_model)
            .join(model, model.id == grant_model.note_id)
            .where(
                model.campaign_id == campaign_id,
                grant_model.user_id == user_id,
            )
        ).all()
        for grant in user_grants:
            db.delete(grant)
    db.flush()


def has_personal_note_access(
    db,
    *,
    campaign_id: int,
    user_id: int,
) -> bool:
    for model, grant_model in PROTECTED_NOTE_DEFINITIONS.values():
        owned = db.exec(
            select(model.id)
            .where(
                model.campaign_id == campaign_id,
                model.access_owner_user_id == user_id,
            )
            .limit(1)
        ).first()
        if owned is not None:
            return True
        granted = db.exec(
            select(grant_model.id)
            .join(model, model.id == grant_model.note_id)
            .where(
                model.campaign_id == campaign_id,
                grant_model.user_id == user_id,
            )
            .limit(1)
        ).first()
        if granted is not None:
            return True
    return False
