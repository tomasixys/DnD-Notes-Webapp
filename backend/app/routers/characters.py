from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.authorization.dependencies import (
    get_shared_read_context,
    get_shared_write_context,
)
from app.models.api import (
    BackstoryNoteRead,
    CharacterDeleteResponse,
    CharacterCreate,
    CharacterNoteData,
    CharacterNoteRead,
    CharacterRead,
    CharacterUpdate,
    DeleteResponse,
)
from app.authorization.context import CampaignContext
from app.services.character_notes import (
    BackstoryNoteService,
    CharacterNoteService,
)
from app.services.characters import CharacterService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/characters",
    tags=["characters"],
)


@router.get("/active")
def get_active_character(
    context: CampaignContext = Depends(get_shared_read_context),
) -> CharacterRead | None:
    return CharacterService(context).get_active()


@router.get("/{person_id}")
def get_character(
    person_id: int,
    context: CampaignContext = Depends(get_shared_read_context),
) -> CharacterRead:
    characters = CharacterService(context)
    return characters.to_read(characters.get_profile(person_id))


@router.post("")
def create_character(
    character: CharacterCreate,
    context: CampaignContext = Depends(get_shared_write_context),
) -> CharacterRead:
    return CharacterService(context).create(character)


@router.put("/{person_id}")
def update_character(
    person_id: int,
    updated_character: CharacterUpdate,
    context: CampaignContext = Depends(get_shared_write_context),
    expected_revision: int = Query(..., ge=1),
    expected_person_revision: int = Query(..., ge=1),
) -> CharacterRead:
    return CharacterService(context).update(
        person_id,
        updated_character,
        expected_revision,
        expected_person_revision,
    )


@router.post("/{person_id}/activate")
def activate_character(
    person_id: int,
    context: CampaignContext = Depends(get_shared_write_context),
) -> CharacterRead:
    return CharacterService(context).activate(person_id)


@router.delete("/{person_id}")
def delete_character(
    person_id: int,
    context: CampaignContext = Depends(get_shared_write_context),
    expected_revision: int = Query(..., ge=1),
) -> CharacterDeleteResponse:
    return CharacterService(context).delete(
        person_id,
        expected_revision,
    )


@router.put("/{person_id}/image")
def update_character_image(
    person_id: int,
    image: UploadFile = File(...),
    context: CampaignContext = Depends(get_shared_write_context),
    expected_revision: int = Query(..., ge=1),
) -> CharacterRead:
    return CharacterService(context).replace_portrait(
        person_id,
        image,
        expected_revision,
    )


@router.delete("/{person_id}/image")
def delete_character_image(
    person_id: int,
    context: CampaignContext = Depends(get_shared_write_context),
    expected_revision: int = Query(..., ge=1),
) -> CharacterRead:
    return CharacterService(context).remove_portrait(
        person_id,
        expected_revision,
    )


@router.get("/{person_id}/notes")
def get_character_notes(
    person_id: int,
    context: CampaignContext = Depends(get_shared_read_context),
) -> list[CharacterNoteRead]:
    return CharacterNoteService(context).list_for_character(person_id)


@router.post("/{person_id}/notes")
def create_character_note(
    person_id: int,
    note: CharacterNoteData,
    context: CampaignContext = Depends(get_shared_write_context),
) -> CharacterNoteRead:
    return CharacterNoteService(context).create(person_id, note)


@router.get("/{person_id}/notes/{note_id}")
def get_character_note(
    person_id: int,
    note_id: int,
    context: CampaignContext = Depends(get_shared_read_context),
) -> CharacterNoteRead:
    service = CharacterNoteService(context)
    return service.to_read(service.get(person_id, note_id))


@router.put("/{person_id}/notes/{note_id}")
def update_character_note(
    person_id: int,
    note_id: int,
    note: CharacterNoteData,
    context: CampaignContext = Depends(get_shared_write_context),
    expected_revision: int = Query(..., ge=1),
) -> CharacterNoteRead:
    return CharacterNoteService(context).update(
        person_id,
        note_id,
        note,
        expected_revision,
    )


@router.delete("/{person_id}/notes/{note_id}")
def delete_character_note(
    person_id: int,
    note_id: int,
    context: CampaignContext = Depends(get_shared_write_context),
    expected_revision: int = Query(..., ge=1),
) -> DeleteResponse:
    return CharacterNoteService(context).delete(
        person_id,
        note_id,
        expected_revision,
    )


@router.get("/{person_id}/backstory")
def get_backstory_notes(
    person_id: int,
    context: CampaignContext = Depends(get_shared_read_context),
) -> list[BackstoryNoteRead]:
    return BackstoryNoteService(context).list_for_character(person_id)


@router.post("/{person_id}/backstory")
def create_backstory_note(
    person_id: int,
    note: CharacterNoteData,
    context: CampaignContext = Depends(get_shared_write_context),
) -> BackstoryNoteRead:
    return BackstoryNoteService(context).create(person_id, note)


@router.get("/{person_id}/backstory/{note_id}")
def get_backstory_note(
    person_id: int,
    note_id: int,
    context: CampaignContext = Depends(get_shared_read_context),
) -> BackstoryNoteRead:
    service = BackstoryNoteService(context)
    return service.to_read(service.get(person_id, note_id))


@router.put("/{person_id}/backstory/{note_id}")
def update_backstory_note(
    person_id: int,
    note_id: int,
    note: CharacterNoteData,
    context: CampaignContext = Depends(get_shared_write_context),
    expected_revision: int = Query(..., ge=1),
) -> BackstoryNoteRead:
    return BackstoryNoteService(context).update(
        person_id,
        note_id,
        note,
        expected_revision,
    )


@router.delete("/{person_id}/backstory/{note_id}")
def delete_backstory_note(
    person_id: int,
    note_id: int,
    context: CampaignContext = Depends(get_shared_write_context),
    expected_revision: int = Query(..., ge=1),
) -> DeleteResponse:
    return BackstoryNoteService(context).delete(
        person_id,
        note_id,
        expected_revision,
    )
