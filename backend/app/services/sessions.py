from fastapi import HTTPException
from sqlmodel import select

from app.models.api import (
    CampaignBackupSession,
    DeleteResponse,
    SessionNoteData,
    SessionNoteRead,
)
from app.models.database import SessionNote
from app.models.enums import ResourceType
from app.services.campaign_context import CampaignContext
from app.services.rolls import RollService
from app.services.tags import TagService


class SessionNoteService:
    def __init__(
        self,
        context: CampaignContext,
        rolls: RollService | None = None,
    ):
        self.context = context
        self.db = context.db
        self.rolls = rolls or RollService(context)
        self.tags = TagService(context)

    def to_read(self, session_note: SessionNote) -> SessionNoteRead:
        return SessionNoteRead(
            id=session_note.id,
            campaign_id=session_note.campaign_id,
            date=session_note.date,
            title=session_note.title,
            description=session_note.content,
            session_number=session_note.session_number,
            tags=self.tags.list_tag_reads(
                ResourceType.SESSION,
                session_note.id,
            ),
        )

    def get(
        self,
        session_note_id: int,
    ) -> SessionNote:
        session_note = self.db.get(SessionNote, session_note_id)
        if (
            session_note is None
            or session_note.campaign_id != self.context.campaign_id
        ):
            raise HTTPException(status_code=404, detail="Session not found")
        return session_note

    def get_by_number(
        self,
        session_number: int,
    ) -> SessionNote | None:
        statement = select(SessionNote).where(
            SessionNote.campaign_id == self.context.campaign_id,
            SessionNote.session_number == session_number,
        )
        return self.db.exec(statement).first()

    def list_for_campaign(self) -> list[SessionNoteRead]:
        statement = (
            select(SessionNote)
            .where(SessionNote.campaign_id == self.context.campaign_id)
            .order_by(SessionNote.session_number.desc())
        )
        return [
            self.to_read(session_note)
            for session_note in self.db.exec(statement).all()
        ]

    def _stage_insert(
        self,
        *,
        date: str,
        title: str,
        description: str,
        session_number: int,
        tags: list[str],
    ) -> SessionNote:
        if self.get_by_number(session_number) is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A session with this session number already exists "
                    "for this campaign"
                ),
            )

        session_note = SessionNote(
            campaign_id=self.context.campaign_id,
            date=date,
            title=title,
            content=description,
            session_number=session_number,
        )
        self.db.add(session_note)
        self.db.flush()
        self.tags.stage_sync_tags(
            ResourceType.SESSION,
            session_note.id,
            tags,
        )
        self.tags.stage_refresh_references(
            ResourceType.SESSION,
            session_note.id,
        )
        return session_note

    def stage_create(
        self,
        session_data: SessionNoteData,
    ) -> SessionNote:
        return self._stage_insert(
            date=session_data.date,
            title=session_data.title,
            description=session_data.description,
            session_number=session_data.session_number,
            tags=session_data.tags,
        )

    def create(
        self,
        session_data: SessionNoteData,
    ) -> SessionNoteRead:
        try:
            session_note = self.stage_create(session_data)
            self.db.commit()
            self.db.refresh(session_note)
            return self.to_read(session_note)
        except Exception:
            self.db.rollback()
            raise

    def stage_update(
        self,
        session_note_id: int,
        session_data: SessionNoteData,
    ) -> SessionNote:
        session_note = self.get(session_note_id)
        previous_labels = [
            session_note.title,
            str(session_note.session_number),
            f"session {session_note.session_number}",
        ]
        existing = self.get_by_number(
            session_data.session_number,
        )
        if existing is not None and existing.id != session_note.id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A different session with this session number already "
                    "exists for this campaign "
                    f"(Session ID: {existing.id})"
                ),
            )

        session_note.session_number = session_data.session_number
        session_note.date = session_data.date
        session_note.title = session_data.title
        session_note.content = session_data.description
        self.db.add(session_note)
        self.db.flush()
        self.tags.stage_sync_tags(
            ResourceType.SESSION,
            session_note.id,
            session_data.tags,
        )
        self.tags.stage_refresh_references(
            ResourceType.SESSION,
            session_note.id,
            previous_labels=previous_labels,
        )
        return session_note

    def update(
        self,
        session_note_id: int,
        session_data: SessionNoteData,
    ) -> SessionNoteRead:
        try:
            session_note = self.stage_update(
                session_note_id,
                session_data,
            )
            self.db.commit()
            self.db.refresh(session_note)
            return self.to_read(session_note)
        except Exception:
            self.db.rollback()
            raise

    def stage_delete(
        self,
        session_note_id: int,
    ) -> None:
        session_note = self.get(session_note_id)
        self.tags.stage_handle_resource_deletion(
            ResourceType.SESSION,
            session_note.id,
        )
        self.db.delete(session_note)
        self.db.flush()

    def delete(
        self,
        session_note_id: int,
    ) -> DeleteResponse:
        try:
            self.stage_delete(session_note_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return DeleteResponse(deleted_id=session_note_id)

    def to_backup(
        self,
        session_note: SessionNote,
    ) -> CampaignBackupSession:
        return CampaignBackupSession(
            date=session_note.date,
            title=session_note.title,
            description=session_note.content,
            session_number=session_note.session_number,
            tags=self.tags.list_values(
                ResourceType.SESSION,
                session_note.id,
            ),
            rolls=self.rolls.get_values_for_session(session_note.id),
        )

    def list_backup_entries(self) -> list[CampaignBackupSession]:
        session_notes = self.db.exec(
            select(SessionNote)
            .where(
                SessionNote.campaign_id == self.context.campaign_id
            )
            .order_by(SessionNote.session_number, SessionNote.id)
        ).all()
        return [
            self.to_backup(session_note)
            for session_note in session_notes
        ]

    def stage_restore(
        self,
        session_backup: CampaignBackupSession,
    ) -> SessionNote:
        session_note = self._stage_insert(
            date=session_backup.date,
            title=session_backup.title,
            description=session_backup.description,
            session_number=session_backup.session_number,
            tags=session_backup.tags,
        )
        self.rolls.stage_restore_for_session(
            session_note,
            session_backup.rolls,
        )
        return session_note
