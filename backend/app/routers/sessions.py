from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.database.models import SessionNote
from app.api.models import (
    ResourceType,
    SessionNoteData,
    SessionNoteRead,
)
from app.routers.campaigns import verify_campaign
from app.tag_handler import (
    get_resource_tag_reads,
    handle_resource_deleted,
    resolve_pending_tags_for_resource,
    sync_resource_tags,
)

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/sessions",
    tags=["sessions"],
)


def session_note_to_read(
    session_note: SessionNote,
    db: Session,
) -> SessionNoteRead:
    return SessionNoteRead(
        id=session_note.id,
        campaign_id=session_note.campaign_id,
        date=session_note.date,
        title=session_note.title,
        description=session_note.description,
        session_number=session_note.session_number,
        tags=get_resource_tag_reads(db, ResourceType.SESSION, session_note.id),
    )


def get_session_note_by_id(
    campaign_id: int,
    session_note_id: int,
    db: Session,
) -> SessionNote | None:
    verify_campaign(campaign_id, db)

    session_note = db.get(SessionNote, session_note_id)
    if session_note is None or session_note.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_note


def get_session_note_by_number(
    campaign_id: int,
    session_number: int,
    db: Session,
) -> SessionNote | None:
    verify_campaign(campaign_id, db)

    statement = (
        select(SessionNote)
        .where(SessionNote.campaign_id == campaign_id)
        .where(SessionNote.session_number == session_number)
    )
    session_note = db.exec(statement).first()
    return session_note

def get_all_sessions_for_campaign(campaign_id: int, db: Session) -> list[SessionNote]:
    verify_campaign(campaign_id, db)
    statement = (
        select(SessionNote)
        .where(SessionNote.campaign_id == campaign_id)
        .order_by(SessionNote.session_number.desc())
    )
    return db.exec(statement).all()

@router.get("")
def get_sessions_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    return [
        session_note_to_read(session_note, db)
        for session_note in get_all_sessions_for_campaign(campaign_id, db)
    ]


@router.get("/{session_note_id}")
def get_session_note(
    campaign_id: int,
    session_note_id: int,
    db: Session = Depends(get_session),
):
    return session_note_to_read(
        get_session_note_by_id(campaign_id, session_note_id, db), db
    )


@router.post("")
def create_session_note(
    campaign_id: int,
    session_note: SessionNoteData,
    db: Session = Depends(get_session),
):
    existing_session = get_session_note_by_number(campaign_id, session_note.session_number, db)

    if existing_session is not None:
        raise HTTPException(
            status_code=409,
            detail="A session with this session number already exists for this campaign",
        )

    db_session_note = SessionNote(
        campaign_id=campaign_id,
        date=session_note.date,
        title=session_note.title,
        description=session_note.description,
        session_number=session_note.session_number,
    )
    db.add(db_session_note)
    db.flush()
    sync_resource_tags(
        db,
        campaign_id,
        ResourceType.SESSION,
        db_session_note.id,
        session_note.tags,
    )
    resolve_pending_tags_for_resource(
        db, campaign_id, ResourceType.SESSION, db_session_note.title
    )
    db.commit()
    db.refresh(db_session_note)

    return session_note_to_read(db_session_note, db)


@router.put("/{session_note_id}")
def update_session_note(
    campaign_id: int,
    session_note_id: int,
    updated_session: SessionNoteData,
    db: Session = Depends(get_session),
):
    session_note = get_session_note_by_id(campaign_id, session_note_id, db)
    existing_session_with_number = get_session_note_by_number(campaign_id, updated_session.session_number, db)

    if (existing_session_with_number is not None and existing_session_with_number.id != session_note.id):
        detail = f"A different session with this session number already exists for this campaign (Session ID: {existing_session_with_number.id})"
        raise HTTPException(status_code=409, detail=detail)

    session_note.session_number = updated_session.session_number
    session_note.date = updated_session.date
    session_note.title = updated_session.title
    session_note.description = updated_session.description
    db.add(session_note)
    db.flush()
    sync_resource_tags(
        db,
        campaign_id,
        ResourceType.SESSION,
        session_note.id,
        updated_session.tags,
    )
    resolve_pending_tags_for_resource(
        db, campaign_id, ResourceType.SESSION, session_note.title
    )
    db.commit()
    db.refresh(session_note)

    return session_note_to_read(session_note, db)


@router.delete("/{session_note_id}")
def delete_session_note(
    campaign_id: int,
    session_note_id: int,
    db: Session = Depends(get_session),
):
    session_note = get_session_note_by_id(campaign_id, session_note_id, db)
    handle_resource_deleted(db, ResourceType.SESSION, session_note.id)
    db.delete(session_note)
    db.commit()

    return {"deleted": True}
