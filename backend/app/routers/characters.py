from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from app.database import get_session
from app.dependencies.campaigns import verify_campaign
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
    Campaign,
    CharacterProfile,
)
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
    campaign: Campaign,
    db: Session,
) -> CharacterRead:
    return CharacterService(db).to_read(profile, campaign)


def get_character_profile(
    campaign_id: int,
    person_id: int,
    db: Session,
) -> CharacterProfile:
    campaign = verify_campaign(campaign_id, db)
    return CharacterService(db).get_profile(campaign, person_id)


@router.get("/active")
def get_active_character(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> CharacterRead | None:
    campaign = verify_campaign(campaign_id, db)
    return CharacterService(db).get_active(campaign)


@router.get("/{person_id}")
def get_character(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    characters = CharacterService(db)
    return characters.to_read(
        characters.get_profile(campaign, person_id),
        campaign,
    )


@router.post("")
def create_character(
    campaign_id: int,
    character: CharacterCreate,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    return CharacterService(db).create(campaign, character)


@router.put("/{person_id}")
def update_character(
    campaign_id: int,
    person_id: int,
    updated_character: CharacterUpdate,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    return CharacterService(db).update(
        campaign,
        person_id,
        updated_character,
    )


@router.post("/{person_id}/activate")
def activate_character(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    return CharacterService(db).activate(campaign, person_id)


@router.delete("/{person_id}")
def delete_character(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    CharacterService(db).delete(campaign, person_id)
    return {"deleted": True}


@router.put("/{person_id}/image")
def update_character_image(
    campaign_id: int,
    person_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    profile = get_character_profile(campaign_id, person_id, db)
    old_image_path = profile.image_path
    saved_image_path: str | None = None

    try:
        saved_image_path = save_image_from_uploadfile(campaign_id, image)
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
    return character_to_read(profile, campaign, db)


@router.delete("/{person_id}/image")
def delete_character_image(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    profile = get_character_profile(campaign_id, person_id, db)
    image_path = profile.image_path
    profile.image_path = ""
    db.add(profile)
    db.commit()
    db.refresh(profile)
    if image_path:
        delete_uploaded_file(image_path)
    return character_to_read(profile, campaign, db)


@router.get("/{person_id}/notes")
def get_character_notes(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
) -> list[CharacterNoteRead]:
    campaign = verify_campaign(campaign_id, db)
    return CharacterNoteService(db).list_for_character(campaign, person_id)


@router.post("/{person_id}/notes")
def create_character_note(
    campaign_id: int,
    person_id: int,
    note: CharacterNoteData,
    db: Session = Depends(get_session),
) -> CharacterNoteRead:
    campaign = verify_campaign(campaign_id, db)
    return CharacterNoteService(db).create(campaign, person_id, note)


@router.get("/{person_id}/notes/{note_id}")
def get_character_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    db: Session = Depends(get_session),
) -> CharacterNoteRead:
    campaign = verify_campaign(campaign_id, db)
    service = CharacterNoteService(db)
    return service.to_read(service.get(campaign, person_id, note_id))


@router.put("/{person_id}/notes/{note_id}")
def update_character_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    note: CharacterNoteData,
    db: Session = Depends(get_session),
) -> CharacterNoteRead:
    campaign = verify_campaign(campaign_id, db)
    return CharacterNoteService(db).update(
        campaign,
        person_id,
        note_id,
        note,
    )


@router.delete("/{person_id}/notes/{note_id}")
def delete_character_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    CharacterNoteService(db).delete(campaign, person_id, note_id)
    return {"deleted": True}


@router.get("/{person_id}/backstory")
def get_backstory_notes(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
) -> list[BackstoryNoteRead]:
    campaign = verify_campaign(campaign_id, db)
    return BackstoryNoteService(db).list_for_character(campaign, person_id)


@router.post("/{person_id}/backstory")
def create_backstory_note(
    campaign_id: int,
    person_id: int,
    note: CharacterNoteData,
    db: Session = Depends(get_session),
) -> BackstoryNoteRead:
    campaign = verify_campaign(campaign_id, db)
    return BackstoryNoteService(db).create(campaign, person_id, note)


@router.get("/{person_id}/backstory/{note_id}")
def get_backstory_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    db: Session = Depends(get_session),
) -> BackstoryNoteRead:
    campaign = verify_campaign(campaign_id, db)
    service = BackstoryNoteService(db)
    return service.to_read(service.get(campaign, person_id, note_id))


@router.put("/{person_id}/backstory/{note_id}")
def update_backstory_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    note: CharacterNoteData,
    db: Session = Depends(get_session),
) -> BackstoryNoteRead:
    campaign = verify_campaign(campaign_id, db)
    return BackstoryNoteService(db).update(
        campaign,
        person_id,
        note_id,
        note,
    )


@router.delete("/{person_id}/backstory/{note_id}")
def delete_backstory_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    BackstoryNoteService(db).delete(campaign, person_id, note_id)
    return {"deleted": True}
