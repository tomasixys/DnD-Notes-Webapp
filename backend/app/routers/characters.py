from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies.campaigns import get_campaign_context
from app.file_storage import (
    delete_uploaded_file,
    save_image_from_uploadfile,
)
from app.models.api import (
    BackstoryNoteRead,
    CharacterCreate,
    CharacterNoteData,
    CharacterNoteRead,
    CharacterRead,
    CharacterUpdate,
)
from app.models.database import (
    CharacterProfile,
)
from app.services.campaign_context import CampaignContext
from app.services.character_notes import (
    BackstoryNoteService,
    CharacterNoteService,
)
from app.services.characters import CharacterService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/characters",
    tags=["characters"],
)


def character_to_read(
    profile: CharacterProfile,
    context: CampaignContext,
) -> CharacterRead:
    return CharacterService(context).to_read(profile)


def get_character_profile(
    person_id: int,
    context: CampaignContext,
) -> CharacterProfile:
    return CharacterService(context).get_profile(person_id)


@router.get("/active")
def get_active_character(
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterRead | None:
    return CharacterService(context).get_active()


@router.get("/{person_id}")
def get_character(
    person_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterRead:
    characters = CharacterService(context)
    return characters.to_read(characters.get_profile(person_id))


@router.post("")
def create_character(
    character: CharacterCreate,
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterRead:
    return CharacterService(context).create(character)


@router.put("/{person_id}")
def update_character(
    person_id: int,
    updated_character: CharacterUpdate,
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterRead:
    return CharacterService(context).update(person_id, updated_character)


@router.post("/{person_id}/activate")
def activate_character(
    person_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterRead:
    return CharacterService(context).activate(person_id)


@router.delete("/{person_id}")
def delete_character(
    person_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    CharacterService(context).delete(person_id)
    return {"deleted": True}


@router.put("/{person_id}/image")
def update_character_image(
    person_id: int,
    image: UploadFile = File(...),
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterRead:
    db = context.db
    profile = get_character_profile(person_id, context)
    old_image_path = profile.image_path
    saved_image_path: str | None = None

    try:
        saved_image_path = save_image_from_uploadfile(
            context.campaign_id,
            image,
        )
        profile.image_path = saved_image_path
        db.add(profile)
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        if saved_image_path:
            delete_uploaded_file(saved_image_path)
        raise

    if old_image_path:
        delete_uploaded_file(old_image_path)
    return character_to_read(profile, context)


@router.delete("/{person_id}/image")
def delete_character_image(
    person_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterRead:
    db = context.db
    profile = get_character_profile(person_id, context)
    image_path = profile.image_path
    profile.image_path = ""
    db.add(profile)
    db.commit()
    db.refresh(profile)
    if image_path:
        delete_uploaded_file(image_path)
    return character_to_read(profile, context)


@router.get("/{person_id}/notes")
def get_character_notes(
    person_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> list[CharacterNoteRead]:
    return CharacterNoteService(context).list_for_character(person_id)


@router.post("/{person_id}/notes")
def create_character_note(
    person_id: int,
    note: CharacterNoteData,
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterNoteRead:
    return CharacterNoteService(context).create(person_id, note)


@router.get("/{person_id}/notes/{note_id}")
def get_character_note(
    person_id: int,
    note_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterNoteRead:
    service = CharacterNoteService(context)
    return service.to_read(service.get(person_id, note_id))


@router.put("/{person_id}/notes/{note_id}")
def update_character_note(
    person_id: int,
    note_id: int,
    note: CharacterNoteData,
    context: CampaignContext = Depends(get_campaign_context),
) -> CharacterNoteRead:
    return CharacterNoteService(context).update(person_id, note_id, note)


@router.delete("/{person_id}/notes/{note_id}")
def delete_character_note(
    person_id: int,
    note_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    CharacterNoteService(context).delete(person_id, note_id)
    return {"deleted": True}


@router.get("/{person_id}/backstory")
def get_backstory_notes(
    person_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> list[BackstoryNoteRead]:
    return BackstoryNoteService(context).list_for_character(person_id)


@router.post("/{person_id}/backstory")
def create_backstory_note(
    person_id: int,
    note: CharacterNoteData,
    context: CampaignContext = Depends(get_campaign_context),
) -> BackstoryNoteRead:
    return BackstoryNoteService(context).create(person_id, note)


@router.get("/{person_id}/backstory/{note_id}")
def get_backstory_note(
    person_id: int,
    note_id: int,
    context: CampaignContext = Depends(get_campaign_context),
) -> BackstoryNoteRead:
    service = BackstoryNoteService(context)
    return service.to_read(service.get(person_id, note_id))


@router.put("/{person_id}/backstory/{note_id}")
def update_backstory_note(
    person_id: int,
    note_id: int,
    note: CharacterNoteData,
    context: CampaignContext = Depends(get_campaign_context),
) -> BackstoryNoteRead:
    return BackstoryNoteService(context).update(person_id, note_id, note)


@router.delete("/{person_id}/backstory/{note_id}")
def delete_backstory_note(
    person_id: int,
    note_id: int,
    context: CampaignContext = Depends(get_campaign_context),
):
    BackstoryNoteService(context).delete(person_id, note_id)
    return {"deleted": True}
