from datetime import datetime, timezone
from typing import TypeVar

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies.campaigns import verify_campaign
from app.inventory_service import sync_default_inventory_owner
from app.file_storage import (
    build_upload_url,
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
    BackstoryNote,
    Campaign,
    CharacterNote,
    CharacterProfile,
)
from app.models.enums import ResourceType
from app.services.people import PersonService
from app.tags import (
    get_resource_tag_reads,
    handle_tags_of_deleted_resource,
    refresh_reference_tags_for_resource,
    sync_resource_tags,
)


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/characters",
    tags=["characters"],
)

PersonalNoteModel = TypeVar(
    "PersonalNoteModel",
    CharacterNote,
    BackstoryNote,
)
PersonalNoteRead = TypeVar(
    "PersonalNoteRead",
    CharacterNoteRead,
    BackstoryNoteRead,
)


def character_to_read(
    profile: CharacterProfile,
    campaign: Campaign,
    db: Session,
) -> CharacterRead:
    people = PersonService(db)
    person = people.get(campaign, profile.person_id)
    return CharacterRead(
        person=people.to_read(person),
        short_bio=profile.short_bio,
        appearance=profile.appearance,
        image_url=(
            build_upload_url(profile.image_path)
            if profile.image_path
            else ""
        ),
        is_active=campaign.active_character_person_id == profile.person_id,
    )


def get_character_profile(
    campaign_id: int,
    person_id: int,
    db: Session,
) -> CharacterProfile:
    campaign = verify_campaign(campaign_id, db)
    PersonService(db).get(campaign, person_id)
    profile = db.get(CharacterProfile, person_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Character profile not found")
    return profile


def personal_note_to_read(
    note: CharacterNote | BackstoryNote,
    resource_type: ResourceType,
    read_model: type[PersonalNoteRead],
    db: Session,
) -> PersonalNoteRead:
    return read_model(
        id=note.id,
        campaign_id=note.campaign_id,
        character_person_id=note.character_person_id,
        title=note.title,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
        tags=get_resource_tag_reads(db, resource_type, note.id),
    )


def get_personal_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    note_model: type[PersonalNoteModel],
    db: Session,
) -> PersonalNoteModel:
    get_character_profile(campaign_id, person_id, db)
    note = db.get(note_model, note_id)
    if (
        note is None
        or note.campaign_id != campaign_id
        or note.character_person_id != person_id
    ):
        raise HTTPException(status_code=404, detail="Character note not found")
    return note


def list_personal_notes(
    campaign_id: int,
    person_id: int,
    note_model: type[PersonalNoteModel],
    resource_type: ResourceType,
    read_model: type[PersonalNoteRead],
    db: Session,
) -> list[PersonalNoteRead]:
    get_character_profile(campaign_id, person_id, db)
    statement = (
        select(note_model)
        .where(
            note_model.campaign_id == campaign_id,
            note_model.character_person_id == person_id,
        )
        .order_by(note_model.updated_at.desc(), note_model.id.desc())
    )
    return [
        personal_note_to_read(note, resource_type, read_model, db)
        for note in db.exec(statement).all()
    ]


def create_personal_note(
    campaign_id: int,
    person_id: int,
    note_data: CharacterNoteData,
    note_model: type[PersonalNoteModel],
    resource_type: ResourceType,
    read_model: type[PersonalNoteRead],
    db: Session,
) -> PersonalNoteRead:
    get_character_profile(campaign_id, person_id, db)
    title = note_data.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Note title cannot be blank")

    note = note_model(
        campaign_id=campaign_id,
        character_person_id=person_id,
        title=title,
        content=note_data.content.strip(),
    )
    db.add(note)
    db.flush()
    sync_resource_tags(
        db, campaign_id, resource_type, note.id, note_data.tags
    )
    refresh_reference_tags_for_resource(
        db, campaign_id, resource_type, note.id
    )
    db.commit()
    db.refresh(note)
    return personal_note_to_read(note, resource_type, read_model, db)


def update_personal_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    note_data: CharacterNoteData,
    note_model: type[PersonalNoteModel],
    resource_type: ResourceType,
    read_model: type[PersonalNoteRead],
    db: Session,
) -> PersonalNoteRead:
    note = get_personal_note(
        campaign_id, person_id, note_id, note_model, db
    )
    title = note_data.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Note title cannot be blank")

    previous_title = note.title
    note.title = title
    note.content = note_data.content.strip()
    note.updated_at = datetime.now(timezone.utc)
    db.add(note)
    db.flush()
    sync_resource_tags(
        db, campaign_id, resource_type, note.id, note_data.tags
    )
    refresh_reference_tags_for_resource(
        db,
        campaign_id,
        resource_type,
        note.id,
        previous_labels=[previous_title],
    )
    db.commit()
    db.refresh(note)
    return personal_note_to_read(note, resource_type, read_model, db)


def delete_personal_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    note_model: type[PersonalNoteModel],
    resource_type: ResourceType,
    db: Session,
):
    note = get_personal_note(
        campaign_id, person_id, note_id, note_model, db
    )
    handle_tags_of_deleted_resource(db, resource_type, note.id)
    db.delete(note)
    db.commit()
    return {"deleted": True}


@router.get("/active")
def get_active_character(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> CharacterRead | None:
    campaign = verify_campaign(campaign_id, db)
    if campaign.active_character_person_id is None:
        return None

    profile = db.get(CharacterProfile, campaign.active_character_person_id)
    if profile is None:
        campaign.active_character_person_id = None
        db.add(campaign)
        db.commit()
        return None

    return character_to_read(profile, campaign, db)


@router.get("/{person_id}")
def get_character(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    profile = get_character_profile(campaign_id, person_id, db)
    return character_to_read(profile, campaign, db)


@router.post("")
def create_character(
    campaign_id: int,
    character: CharacterCreate,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    has_person_id = character.person_id is not None
    has_person_data = character.person is not None
    if has_person_id == has_person_data:
        raise HTTPException(
            status_code=422,
            detail="Provide either person_id or person, but not both",
        )

    people = PersonService(db)
    if character.person_id is not None:
        person = people.get(campaign, character.person_id)
    else:
        person = people.add(campaign, character.person)

    if db.get(CharacterProfile, person.id) is not None:
        raise HTTPException(
            status_code=409,
            detail="This person already has a character profile",
        )

    profile = CharacterProfile(
        person_id=person.id,
        short_bio=character.short_bio.strip(),
        appearance=character.appearance.strip(),
    )
    db.add(profile)
    db.flush()

    if character.make_active:
        campaign.active_character_person_id = person.id
        db.add(campaign)
        sync_default_inventory_owner(campaign, db)

    db.commit()
    db.refresh(profile)
    db.refresh(campaign)
    return character_to_read(profile, campaign, db)


@router.put("/{person_id}")
def update_character(
    campaign_id: int,
    person_id: int,
    updated_character: CharacterUpdate,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    profile = get_character_profile(campaign_id, person_id, db)

    people = PersonService(db)
    people.apply_changes(
        campaign,
        person_id,
        updated_character.person,
    )
    profile.short_bio = updated_character.short_bio.strip()
    profile.appearance = updated_character.appearance.strip()
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return character_to_read(profile, campaign, db)


@router.post("/{person_id}/activate")
def activate_character(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
) -> CharacterRead:
    campaign = verify_campaign(campaign_id, db)
    profile = get_character_profile(campaign_id, person_id, db)
    campaign.active_character_person_id = person_id
    db.add(campaign)
    sync_default_inventory_owner(campaign, db)
    db.commit()
    db.refresh(campaign)
    return character_to_read(profile, campaign, db)


@router.delete("/{person_id}")
def delete_character(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)
    profile = get_character_profile(campaign_id, person_id, db)
    portrait_path = profile.image_path
    for note_model, resource_type in (
        (CharacterNote, ResourceType.CHARACTER_NOTE),
        (BackstoryNote, ResourceType.BACKSTORY_NOTE),
    ):
        notes = db.exec(
            select(note_model).where(
                note_model.character_person_id == person_id
            )
        ).all()
        for note in notes:
            handle_tags_of_deleted_resource(db, resource_type, note.id)

    if campaign.active_character_person_id == person_id:
        campaign.active_character_person_id = None
        db.add(campaign)

    db.delete(profile)
    db.commit()
    if portrait_path:
        delete_uploaded_file(portrait_path)
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
    return list_personal_notes(
        campaign_id,
        person_id,
        CharacterNote,
        ResourceType.CHARACTER_NOTE,
        CharacterNoteRead,
        db,
    )


@router.post("/{person_id}/notes")
def create_character_note(
    campaign_id: int,
    person_id: int,
    note: CharacterNoteData,
    db: Session = Depends(get_session),
) -> CharacterNoteRead:
    return create_personal_note(
        campaign_id,
        person_id,
        note,
        CharacterNote,
        ResourceType.CHARACTER_NOTE,
        CharacterNoteRead,
        db,
    )


@router.get("/{person_id}/notes/{note_id}")
def get_character_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    db: Session = Depends(get_session),
) -> CharacterNoteRead:
    note = get_personal_note(
        campaign_id, person_id, note_id, CharacterNote, db
    )
    return personal_note_to_read(
        note, ResourceType.CHARACTER_NOTE, CharacterNoteRead, db
    )


@router.put("/{person_id}/notes/{note_id}")
def update_character_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    note: CharacterNoteData,
    db: Session = Depends(get_session),
) -> CharacterNoteRead:
    return update_personal_note(
        campaign_id,
        person_id,
        note_id,
        note,
        CharacterNote,
        ResourceType.CHARACTER_NOTE,
        CharacterNoteRead,
        db,
    )


@router.delete("/{person_id}/notes/{note_id}")
def delete_character_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    db: Session = Depends(get_session),
):
    return delete_personal_note(
        campaign_id,
        person_id,
        note_id,
        CharacterNote,
        ResourceType.CHARACTER_NOTE,
        db,
    )


@router.get("/{person_id}/backstory")
def get_backstory_notes(
    campaign_id: int,
    person_id: int,
    db: Session = Depends(get_session),
) -> list[BackstoryNoteRead]:
    return list_personal_notes(
        campaign_id,
        person_id,
        BackstoryNote,
        ResourceType.BACKSTORY_NOTE,
        BackstoryNoteRead,
        db,
    )


@router.post("/{person_id}/backstory")
def create_backstory_note(
    campaign_id: int,
    person_id: int,
    note: CharacterNoteData,
    db: Session = Depends(get_session),
) -> BackstoryNoteRead:
    return create_personal_note(
        campaign_id,
        person_id,
        note,
        BackstoryNote,
        ResourceType.BACKSTORY_NOTE,
        BackstoryNoteRead,
        db,
    )


@router.get("/{person_id}/backstory/{note_id}")
def get_backstory_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    db: Session = Depends(get_session),
) -> BackstoryNoteRead:
    note = get_personal_note(
        campaign_id, person_id, note_id, BackstoryNote, db
    )
    return personal_note_to_read(
        note, ResourceType.BACKSTORY_NOTE, BackstoryNoteRead, db
    )


@router.put("/{person_id}/backstory/{note_id}")
def update_backstory_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    note: CharacterNoteData,
    db: Session = Depends(get_session),
) -> BackstoryNoteRead:
    return update_personal_note(
        campaign_id,
        person_id,
        note_id,
        note,
        BackstoryNote,
        ResourceType.BACKSTORY_NOTE,
        BackstoryNoteRead,
        db,
    )


@router.delete("/{person_id}/backstory/{note_id}")
def delete_backstory_note(
    campaign_id: int,
    person_id: int,
    note_id: int,
    db: Session = Depends(get_session),
):
    return delete_personal_note(
        campaign_id,
        person_id,
        note_id,
        BackstoryNote,
        ResourceType.BACKSTORY_NOTE,
        db,
    )
