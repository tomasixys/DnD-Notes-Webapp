from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Campaign, SessionNote
from app.routers.campaigns import verify_campaign

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/sessions",
    tags=["sessions"],
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
    if session_note is None or session_note.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Session not found")

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
    return get_all_sessions_for_campaign(campaign_id, db)


@router.get("/{session_note_id}")
def get_session_note(
    campaign_id: int,
    session_note_id: int,
    db: Session = Depends(get_session),
):
    return get_session_note_by_id(campaign_id, session_note_id, db)


@router.post("")
def create_session_note(
    campaign_id: int,
    session_note: SessionNote,
    db: Session = Depends(get_session),
):
    existing_session = get_session_note_by_number(campaign_id, session_note.session_number, db)

    if existing_session is not None:
        raise HTTPException(
            status_code=409,
            detail="A session with this session number already exists for this campaign",
        )

    session_note.id = None
    session_note.campaign_id = campaign_id

    db.add(session_note)
    db.commit()
    db.refresh(session_note)

    return session_note


@router.put("/{session_note_id}")
def update_session_note(
    campaign_id: int,
    session_note_id: int,
    updated_session: SessionNote,
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
    session_note.tags = updated_session.tags

    db.add(session_note)
    db.commit()
    db.refresh(session_note)

    return session_note


@router.delete("/{session_note_id}")
def delete_session_note(
    campaign_id: int,
    session_note_id: int,
    db: Session = Depends(get_session),
):
    session_note = get_session_note_by_id(campaign_id, session_note_id, db)
    db.delete(session_note)
    db.commit()

    return {"deleted": True}