import json, io
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, Session, select

from app.database import get_session
from app.database.models import *
from app.api.models import *
# from app.app_paths import get_uploads_dir
from app.file_storage import *
from app.tag_handler import (
    get_resource_tags,
    resolve_pending_tags_for_resource,
    sync_resource_tags,
)

router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)

def verify_campaign(campaign_id: int, db: Session) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return campaign


def campaign_to_response(campaign: Campaign, session_count: int = 0):
    image_url = build_upload_url(campaign.image_path) if campaign.image_path else ""
    banner_image_url = build_upload_url(campaign.banner_image_path) if campaign.banner_image_path else image_url

    return {
        "id": campaign.id,
        "name": campaign.name,
        "player_character": campaign.player_character,
        "description": campaign.description,
        "session_count": session_count,
        "image_url": image_url,
        "banner_image_url": banner_image_url,
    }

def sqlmodel_to_dict(model: SQLModel):
    if hasattr(model, "model_dump"):
        return model.model_dump()

    return model.dict()



@router.get("")
def get_campaigns(db: Session = Depends(get_session)):
    statement = (
        select(Campaign, func.count(SessionNote.id))
        .join(
            SessionNote,
            SessionNote.campaign_id == Campaign.id,
            isouter=True,
        )
        .group_by(Campaign.id)
        .order_by(Campaign.id)
    )

    results = db.exec(statement).all()

    return [
        campaign_to_response(
            campaign=campaign,
            session_count=session_count,
        )
        for campaign, session_count in results
    ]


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_session)):
    campaign = verify_campaign(campaign_id, db)

    statement = (
        select(func.count(SessionNote.id))
        .where(SessionNote.campaign_id == campaign_id)
    )
    session_count = db.exec(statement).one()
    return campaign_to_response(campaign=campaign, session_count=session_count)


@router.post("")
def create_campaign(
    name: str = Form(...),
    player_character: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    db: Session = Depends(get_session),
):
    campaign = Campaign(
        name=name,
        player_character=player_character,
        description=description,
        image_path="",
        banner_image_path=""
    )

    db.add(campaign)
    db.flush()  # assigns campaign.id without committing yet

    saved_image_relative_path: str | None = None
    saved_banner_relative_path: str | None = None

    try:
        if image is not None and image.filename:
            saved_image_relative_path = save_image_from_uploadfile(
                campaign_id=campaign.id,
                file=image,
            )
            campaign.image_path = saved_image_relative_path

        if banner is not None and banner.filename:
            saved_banner_relative_path = save_image_from_uploadfile(
                campaign_id=campaign.id,
                file=banner,
            )
            campaign.banner_image_path = saved_banner_relative_path

        db.add(campaign)
        db.commit()
        db.refresh(campaign)

    except Exception:
        db.rollback()

        if saved_image_relative_path is not None:
            delete_uploaded_file(saved_image_relative_path)
        if saved_banner_relative_path is not None:
            delete_uploaded_file(saved_banner_relative_path)

        raise

    return campaign_to_response(campaign, session_count=0)


@router.put("/{campaign_id}")
def update_campaign(
    campaign_id: int,
    name: str = Form(...),
    player_character: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    db: Session = Depends(get_session),
):
    campaign = verify_campaign(campaign_id, db)

    campaign.name = name
    campaign.player_character = player_character
    campaign.description = description

    old_image_path: str | None = None
    old_banner_path: str | None = None
    saved_image_path: str | None = None
    saved_banner_path: str | None = None

    try:
        if image is not None and image.filename:
            old_image_path = campaign.image_path
            saved_image_path = save_image_from_uploadfile(
                campaign_id=campaign.id,
                file=image,
            )
            campaign.image_path = saved_image_path

        if banner is not None and banner.filename:
            old_banner_path = campaign.banner_image_path
            saved_banner_path = save_image_from_uploadfile(
                campaign_id=campaign.id,
                file=banner,
            )
            campaign.banner_image_path = saved_banner_path

        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        if old_image_path is not None:
            delete_uploaded_file(old_image_path)

        if old_banner_path is not None:
            delete_uploaded_file(old_banner_path)

    except Exception:
        db.rollback()

        if saved_image_path is not None:
            delete_uploaded_file(saved_image_path)

        if saved_banner_path is not None:
            delete_uploaded_file(saved_banner_path)

        raise

    statement = (
        select(func.count(SessionNote.id))
        .where(SessionNote.campaign_id == campaign_id)
    )

    session_count = db.exec(statement).one()

    return campaign_to_response(
        campaign=campaign,
        session_count=session_count,
    )


@router.delete("/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_session)
):
    campaign = verify_campaign(campaign_id, db)

    image_path = campaign.image_path
    banner_path = campaign.banner_image_path

    db.delete(campaign)
    db.commit()

    if image_path:
        delete_uploaded_file(image_path)

    if banner_path and banner_path != image_path:
        delete_uploaded_file(banner_path)

    return {"deleted": True}



@router.get("/{campaign_id}/backup/export")
def export_campaign_backup(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    statement = (
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .options(
            selectinload(Campaign.sessions).selectinload(SessionNote.rolls),
            selectinload(Campaign.people),
            selectinload(Campaign.locations),
            selectinload(Campaign.factions),
        )
    )

    campaign = db.exec(statement).one_or_none()

    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    archive_absolute_path, archive_relative_path = make_backup_archive_path(campaign.name)
    image_archive_path = ""
    banner_archive_path = ""

    with ZipFile(archive_absolute_path, "w", compression=ZIP_DEFLATED) as archive:
        if campaign.image_path:
            source_path = get_uploaded_file_path(campaign.image_path)

            if source_path and source_path.exists():
                image_archive_path = f"assets/campaign-image{source_path.suffix.lower()}"
                archive.write(source_path, image_archive_path)

        if campaign.banner_image_path:
            source_path = get_uploaded_file_path(campaign.banner_image_path)

            if source_path and source_path.exists():
                banner_archive_path = f"assets/campaign-banner{source_path.suffix.lower()}"
                archive.write(source_path, banner_archive_path)

        party_stash_backup = None
        if campaign.party_stash:
            party_stash_backup = CampaignBackupPartyStash(
                coins=[
                    CampaignBackupCoinEntry(value=c.value, type=c.type)
                    for c in campaign.party_stash.coins
                ],
                loot=[
                    CampaignBackupLootItem(
                        name=item.name,
                        desc=item.desc,
                        value=CampaignBackupCoinEntry(
                            value=item.value.value, type=item.value.type
                        )
                        if item.value
                        else CampaignBackupCoinEntry(value=0, type="gp"),
                    )
                    for item in campaign.party_stash.loot
                ],
            )

        backup = CampaignBackup(
            schema_version=CAMPAIGN_BACKUP_SCHEMA_VERSION,
            campaign=CampaignBackupCampaign(
                name=campaign.name,
                player_character=campaign.player_character,
                description=campaign.description,
                image_archive_path=image_archive_path,
                banner_archive_path=banner_archive_path,
            ),
            sessions=[
                CampaignBackupSession(
                    date=session.date,
                    title=session.title,
                    description=session.description,
                    session_number=session.session_number,
                    tags=get_resource_tags(
                        db, ResourceType.SESSION, session.id
                    ),
                    rolls=[
                        roll_entry.roll
                        for roll_entry in sorted(
                            session.rolls,
                            key=lambda roll_entry: roll_entry.id or 0,
                        )
                    ],
                )
                for session in sorted(
                    campaign.sessions,
                    key=lambda session: session.session_number,
                )
            ],
            people=[
                CampaignBackupPerson(
                    name=person.name,
                    role=person.role,
                    faction=person.faction,
                    location=person.location,
                    description=person.description,
                    tags=get_resource_tags(
                        db, ResourceType.PERSON, person.id
                    ),
                )
                for person in sorted(campaign.people, key=lambda person: person.name.lower())
            ],
            locations=[
                CampaignBackupLocation(
                    name=location.name,
                    type=location.type,
                    parent_location=location.parent_location,
                    description=location.description,
                    tags=get_resource_tags(
                        db, ResourceType.LOCATION, location.id
                    ),
                )
                for location in sorted(campaign.locations, key=lambda location: location.name.lower())
            ],
            factions=[
                CampaignBackupFaction(
                    name=faction.name,
                    type=faction.type,
                    location=faction.location,
                    description=faction.description,
                    tags=get_resource_tags(
                        db, ResourceType.FACTION, faction.id
                    ),
                )
                for faction in sorted(campaign.factions, key=lambda faction: faction.name.lower())
            ],
            party_stash=party_stash_backup,
        )

        archive.writestr(
            "backup.json",
            json.dumps(sqlmodel_to_dict(backup), ensure_ascii=False, indent=2),
        )

    return {
        "backup_url": build_upload_url(archive_relative_path),
        "filename": archive_absolute_path.name,
    }

@router.post("/backup/import")
async def import_campaign_backup(
    backup: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    try:
        raw_data = await backup.read()

        with ZipFile(io.BytesIO(raw_data), "r") as archive:
            backup_json = archive.read("backup.json")
            parsed_json = json.loads(backup_json.decode("utf-8"))
            cb = CampaignBackup(**parsed_json)

            if cb.schema_version != CAMPAIGN_BACKUP_SCHEMA_VERSION:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported backup schema version: {cb.schema_version}",
                )

            campaign = Campaign(
                name=cb.campaign.name,
                player_character=cb.campaign.player_character,
                description=cb.campaign.description,
                image_path="",
                banner_image_path="",
            )

            saved_asset_paths: list[str] = []

            try:
                db.add(campaign)
                db.flush()

                original_path = Path(cb.campaign.image_archive_path)
                if original_path != "":
                    image_data = read_archive_member(archive, original_path)
                    image_path = write_image_from_bytes(campaign.id, original_path.suffix.lower(), image_data)
                    saved_asset_paths.append(image_path)
                    campaign.image_path = image_path

                original_path = Path(cb.campaign.banner_archive_path)
                if original_path != "":
                    banner_data = read_archive_member(archive, original_path)
                    banner_path = write_image_from_bytes(campaign.id, original_path.suffix.lower(), banner_data)
                    saved_asset_paths.append(banner_path)
                    campaign.banner_image_path = banner_path

                db.add(campaign)

                for person_backup in cb.people:
                    person = Person(
                        campaign_id=campaign.id,
                        name=person_backup.name,
                        role=person_backup.role,
                        faction=person_backup.faction,
                        location=person_backup.location,
                        description=person_backup.description,
                    )
                    db.add(person)
                    db.flush()
                    sync_resource_tags(
                        db,
                        campaign.id,
                        ResourceType.PERSON,
                        person.id,
                        person_backup.tags,
                    )
                    resolve_pending_tags_for_resource(
                        db, campaign.id, ResourceType.PERSON, person.name
                    )

                for location_backup in cb.locations:
                    location = Location(
                        campaign_id=campaign.id,
                        name=location_backup.name,
                        type=location_backup.type,
                        parent_location=location_backup.parent_location,
                        description=location_backup.description,
                    )
                    db.add(location)
                    db.flush()
                    sync_resource_tags(
                        db,
                        campaign.id,
                        ResourceType.LOCATION,
                        location.id,
                        location_backup.tags,
                    )
                    resolve_pending_tags_for_resource(
                        db,
                        campaign.id,
                        ResourceType.LOCATION,
                        location.name,
                    )

                for faction_backup in cb.factions:
                    faction = Faction(
                        campaign_id=campaign.id,
                        name=faction_backup.name,
                        type=faction_backup.type,
                        location=faction_backup.location,
                        description=faction_backup.description,
                    )
                    db.add(faction)
                    db.flush()
                    sync_resource_tags(
                        db,
                        campaign.id,
                        ResourceType.FACTION,
                        faction.id,
                        faction_backup.tags,
                    )
                    resolve_pending_tags_for_resource(
                        db,
                        campaign.id,
                        ResourceType.FACTION,
                        faction.name,
                    )

                for session_backup in cb.sessions:
                    session_note = SessionNote(
                        campaign_id=campaign.id,
                        date=session_backup.date,
                        title=session_backup.title,
                        description=session_backup.description,
                        session_number=session_backup.session_number,
                    )

                    db.add(session_note)
                    db.flush()
                    sync_resource_tags(
                        db,
                        campaign.id,
                        ResourceType.SESSION,
                        session_note.id,
                        session_backup.tags,
                    )
                    resolve_pending_tags_for_resource(
                        db,
                        campaign.id,
                        ResourceType.SESSION,
                        session_note.title,
                    )

                    for roll in session_backup.rolls:
                        db.add(
                            RollEntry(
                                session_id=session_note.id,
                                roll=roll,
                            )
                        )

                if cb.party_stash:
                    party_stash = PartyStash(campaign_id=campaign.id)
                    db.add(party_stash)
                    db.flush()

                    new_coins = []
                    for coin_backup in cb.party_stash.coins:
                        coin_entry = CoinEntry(value=coin_backup.value, type=coin_backup.type)
                        db.add(coin_entry)
                        new_coins.append(coin_entry)
                    db.flush()
                    party_stash.coins = new_coins

                    for item_backup in cb.party_stash.loot:
                        loot_coin_entry = CoinEntry(
                            value=item_backup.value.value,
                            type=item_backup.value.type,
                        )
                        db.add(loot_coin_entry)
                        db.flush()

                        item = LootItem(
                            party_stash_id=party_stash.id,
                            name=item_backup.name,
                            desc=item_backup.desc,
                            coin_entry_id=loot_coin_entry.id,
                        )
                        db.add(item)

                db.commit()
                db.refresh(campaign)


            except Exception:
                db.rollback()

                for asset_path in saved_asset_paths:
                    delete_uploaded_file(asset_path)

                raise

    except BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid backup archive")

    except KeyError:
        raise HTTPException(status_code=400, detail="Backup archive is missing backup.json")

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid backup JSON")

    return campaign_to_response(campaign=campaign, session_count=len(cb.sessions))

