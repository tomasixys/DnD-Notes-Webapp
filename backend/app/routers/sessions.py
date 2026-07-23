from fastapi import APIRouter, Depends

from app.dependencies.campaigns import get_campaign_context
from app.models.api import SessionNoteData
from app.services.campaign_context import CampaignContext
from app.services.sessions import SessionNoteService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/sessions",
    tags=["sessions"],
)


@router.get("")
def get_sessions_for_campaign(
    campaign_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    return SessionNoteService(context).list_for_campaign()


@router.get("/{session_note_id}")
def get_session_note(
    campaign_id: int,
    session_note_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    service = SessionNoteService(context)
    return service.to_read(service.get(session_note_id))


@router.post("")
def create_session_note(
    campaign_id: int,
    session_note: SessionNoteData,
    context: CampaignContext = Depends(get_campaign_context),
):
    return SessionNoteService(context).create(session_note)


@router.put("/{session_note_id}")
def update_session_note(
    campaign_id: int,
    session_note_id: int,
    updated_session: SessionNoteData,
    context: CampaignContext = Depends(get_campaign_context),
):
    return SessionNoteService(context).update(
        session_note_id, updated_session
    )


@router.delete("/{session_note_id}")
def delete_session_note(
    campaign_id: int,
    session_note_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    SessionNoteService(context).delete(session_note_id)
    return {"deleted": True}
