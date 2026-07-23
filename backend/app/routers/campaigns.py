import json, io
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, Session, select

from app.database import get_session
from app.inventory_service import (
    ensure_default_inventory,
    sync_default_inventory_owner,
)
from app.models.database import *
from app.models.api import *
from app.models.enums import CurrencyDenomination
# from app.app_paths import get_uploads_dir
from app.file_storage import *
from app.tags import (
    get_resource_relationship,
    get_resource_tags,
    refresh_reference_tags_for_resource,
    sync_resource_relationship,
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
        "active_character_person_id": campaign.active_character_person_id,
    }

def sqlmodel_to_dict(model: SQLModel):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")

    return model.dict()


def inventory_to_backup(
    inventory: Inventory,
    db: Session,
) -> CampaignBackupInventory:
    balances = {
        balance.denomination: balance.amount
        for balance in db.exec(
            select(CurrencyBalance).where(
                CurrencyBalance.purse_id == inventory.id
            )
        ).all()
    }
    members = db.exec(
        select(InventoryAccess)
        .where(InventoryAccess.inventory_id == inventory.id)
        .order_by(InventoryAccess.character_person_id)
    ).all()
    items = db.exec(
        select(InventoryItem)
        .where(InventoryItem.inventory_id == inventory.id)
        .order_by(InventoryItem.id)
    ).all()

    return CampaignBackupInventory(
        name=inventory.name,
        description=inventory.description,
        purse=CampaignBackupPurse(
            **{
                denomination.value: balances.get(denomination, 0)
                for denomination in CurrencyDenomination
            }
        ),
        members=[
            CampaignBackupInventoryMember(
                person_backup_id=member.character_person_id,
                role=member.role,
            )
            for member in members
        ],
        items=[
            CampaignBackupInventoryItem(
                name=item.name,
                description=item.description,
                category=item.category,
                rarity=item.rarity,
                quantity=item.quantity,
                unit_value_cp=item.unit_value_cp,
            )
            for item in items
        ],
    )


def restore_inventory_backups(
    campaign: Campaign,
    inventory_backups: list[CampaignBackupInventory],
    default_inventory: Inventory,
    person_id_map: dict[int, int],
    db: Session,
) -> None:
    for index, inventory_backup in enumerate(inventory_backups):
        if index == 0:
            inventory = default_inventory
        else:
            inventory = Inventory(campaign_id=campaign.id)
            db.add(inventory)
            db.flush()
            db.add(Purse(inventory_id=inventory.id))
            db.flush()

        inventory.name = inventory_backup.name
        inventory.description = inventory_backup.description
        db.add(inventory)
        db.flush()

        existing_balances = {
            balance.denomination: balance
            for balance in db.exec(
                select(CurrencyBalance).where(
                    CurrencyBalance.purse_id == inventory.id
                )
            ).all()
        }
        for denomination in CurrencyDenomination:
            balance = existing_balances.get(denomination)
            amount = getattr(inventory_backup.purse, denomination.value)
            if balance is None:
                balance = CurrencyBalance(
                    purse_id=inventory.id,
                    denomination=denomination,
                )
            balance.amount = amount
            db.add(balance)

        existing_items = db.exec(
            select(InventoryItem).where(
                InventoryItem.inventory_id == inventory.id
            )
        ).all()
        for item in existing_items:
            db.delete(item)

        existing_grants = db.exec(
            select(InventoryAccess).where(
                InventoryAccess.inventory_id == inventory.id
            )
        ).all()
        for grant in existing_grants:
            db.delete(grant)
        db.flush()

        for item_backup in inventory_backup.items:
            db.add(
                InventoryItem(
                    inventory_id=inventory.id,
                    name=item_backup.name,
                    description=item_backup.description,
                    category=item_backup.category,
                    rarity=item_backup.rarity,
                    quantity=item_backup.quantity,
                    unit_value_cp=item_backup.unit_value_cp,
                )
            )

        for member_backup in inventory_backup.members:
            character_person_id = person_id_map.get(
                member_backup.person_backup_id
            )
            if (
                character_person_id is None
                or db.get(CharacterProfile, character_person_id) is None
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Inventory access references a missing "
                        "character profile"
                    ),
                )
            db.add(
                InventoryAccess(
                    inventory_id=inventory.id,
                    character_person_id=character_person_id,
                    role=member_backup.role,
                )
            )
        db.flush()



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
    ensure_default_inventory(campaign, db)

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
    character_image_paths = [
        profile.image_path
        for profile in db.exec(
            select(CharacterProfile)
            .join(Person, Person.id == CharacterProfile.person_id)
            .where(Person.campaign_id == campaign_id)
        ).all()
        if profile.image_path
    ]

    db.delete(campaign)
    db.commit()

    if image_path:
        delete_uploaded_file(image_path)

    if banner_path and banner_path != image_path:
        delete_uploaded_file(banner_path)

    for character_image_path in character_image_paths:
        delete_uploaded_file(character_image_path)

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

    character_profiles = db.exec(
        select(CharacterProfile)
        .join(Person, Person.id == CharacterProfile.person_id)
        .where(Person.campaign_id == campaign_id)
        .order_by(Person.name)
    ).all()
    inventories = db.exec(
        select(Inventory)
        .where(Inventory.campaign_id == campaign_id)
        .order_by(Inventory.id)
    ).all()

    archive_absolute_path, archive_relative_path = make_backup_archive_path(campaign.name)
    image_archive_path = ""
    banner_archive_path = ""
    character_image_archive_paths: dict[int, str] = {}

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

        for profile in character_profiles:
            if not profile.image_path:
                continue
            source_path = get_uploaded_file_path(profile.image_path)
            if source_path and source_path.exists():
                archive_path = (
                    f"assets/characters/{profile.person_id}-portrait"
                    f"{source_path.suffix.lower()}"
                )
                archive.write(source_path, archive_path)
                character_image_archive_paths[profile.person_id] = archive_path

        backup = CampaignBackup(
            schema_version=CAMPAIGN_BACKUP_SCHEMA_VERSION,
            campaign=CampaignBackupCampaign(
                name=campaign.name,
                player_character=campaign.player_character,
                description=campaign.description,
                image_archive_path=image_archive_path,
                banner_archive_path=banner_archive_path,
                active_character_person_backup_id=(
                    campaign.active_character_person_id
                ),
            ),
            sessions=[
                CampaignBackupSession(
                    date=session.date,
                    title=session.title,
                    description=session.content,
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
                    backup_id=person.id,
                    name=person.name,
                    role=person.role,
                    faction=(
                        relationship.label
                        if (relationship := get_resource_relationship(
                            db,
                            ResourceType.PERSON,
                            person.id,
                            RelationshipType.MEMBER_OF,
                        ))
                        else ""
                    ),
                    location=(
                        relationship.label
                        if (relationship := get_resource_relationship(
                            db,
                            ResourceType.PERSON,
                            person.id,
                            RelationshipType.LOCATED_IN,
                        ))
                        else ""
                    ),
                    description=person.description,
                    tags=get_resource_tags(
                        db, ResourceType.PERSON, person.id
                    ),
                )
                for person in sorted(campaign.people, key=lambda person: person.name.lower())
            ],
            characters=[
                CampaignBackupCharacter(
                    person_backup_id=profile.person_id,
                    short_bio=profile.short_bio,
                    appearance=profile.appearance,
                    image_archive_path=character_image_archive_paths.get(
                        profile.person_id, ""
                    ),
                    notes=[
                        CampaignBackupCharacterNote(
                            title=note.title,
                            content=note.content,
                            tags=get_resource_tags(
                                db,
                                ResourceType.CHARACTER_NOTE,
                                note.id,
                            ),
                            created_at=note.created_at,
                            updated_at=note.updated_at,
                        )
                        for note in sorted(
                            profile.notes,
                            key=lambda item: (item.created_at, item.id or 0),
                        )
                    ],
                    backstory_notes=[
                        CampaignBackupCharacterNote(
                            title=note.title,
                            content=note.content,
                            tags=get_resource_tags(
                                db,
                                ResourceType.BACKSTORY_NOTE,
                                note.id,
                            ),
                            created_at=note.created_at,
                            updated_at=note.updated_at,
                        )
                        for note in sorted(
                            profile.backstory_notes,
                            key=lambda item: (item.created_at, item.id or 0),
                        )
                    ],
                )
                for profile in character_profiles
            ],
            locations=[
                CampaignBackupLocation(
                    name=location.name,
                    type=location.type,
                    parent_location=(
                        relationship.label
                        if (relationship := get_resource_relationship(
                            db,
                            ResourceType.LOCATION,
                            location.id,
                            RelationshipType.PART_OF,
                        ))
                        else ""
                    ),
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
                    location=(
                        relationship.label
                        if (relationship := get_resource_relationship(
                            db,
                            ResourceType.FACTION,
                            faction.id,
                            RelationshipType.BASED_IN,
                        ))
                        else ""
                    ),
                    description=faction.description,
                    tags=get_resource_tags(
                        db, ResourceType.FACTION, faction.id
                    ),
                )
                for faction in sorted(campaign.factions, key=lambda faction: faction.name.lower())
            ],
            inventories=[
                inventory_to_backup(inventory, db)
                for inventory in inventories
            ],
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

            if not 1 <= cb.schema_version <= CAMPAIGN_BACKUP_SCHEMA_VERSION:
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
            person_id_map: dict[int, int] = {}

            try:
                db.add(campaign)
                db.flush()
                default_inventory = ensure_default_inventory(campaign, db)

                original_path = Path(cb.campaign.image_archive_path)
                if cb.campaign.image_archive_path:
                    image_data = read_archive_member(archive, original_path)
                    image_path = write_image_from_bytes(campaign.id, original_path.suffix.lower(), image_data)
                    saved_asset_paths.append(image_path)
                    campaign.image_path = image_path

                original_path = Path(cb.campaign.banner_archive_path)
                if cb.campaign.banner_archive_path:
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
                        description=person_backup.description,
                    )
                    db.add(person)
                    db.flush()
                    if person_backup.backup_id is not None:
                        person_id_map[person_backup.backup_id] = person.id
                    sync_resource_tags(
                        db,
                        campaign.id,
                        ResourceType.PERSON,
                        person.id,
                        person_backup.tags,
                    )
                    sync_resource_relationship(
                        db,
                        campaign.id,
                        ResourceType.PERSON,
                        person.id,
                        RelationshipType.MEMBER_OF,
                        ResourceType.FACTION,
                        person_backup.faction,
                    )
                    sync_resource_relationship(
                        db,
                        campaign.id,
                        ResourceType.PERSON,
                        person.id,
                        RelationshipType.LOCATED_IN,
                        ResourceType.LOCATION,
                        person_backup.location,
                    )
                    refresh_reference_tags_for_resource(
                        db, campaign.id, ResourceType.PERSON, person.id
                    )

                for location_backup in cb.locations:
                    location = Location(
                        campaign_id=campaign.id,
                        name=location_backup.name,
                        type=location_backup.type,
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
                    sync_resource_relationship(
                        db,
                        campaign.id,
                        ResourceType.LOCATION,
                        location.id,
                        RelationshipType.PART_OF,
                        ResourceType.LOCATION,
                        location_backup.parent_location,
                    )
                    refresh_reference_tags_for_resource(
                        db,
                        campaign.id,
                        ResourceType.LOCATION,
                        location.id,
                    )

                for faction_backup in cb.factions:
                    faction = Faction(
                        campaign_id=campaign.id,
                        name=faction_backup.name,
                        type=faction_backup.type,
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
                    sync_resource_relationship(
                        db,
                        campaign.id,
                        ResourceType.FACTION,
                        faction.id,
                        RelationshipType.BASED_IN,
                        ResourceType.LOCATION,
                        faction_backup.location,
                    )
                    refresh_reference_tags_for_resource(
                        db,
                        campaign.id,
                        ResourceType.FACTION,
                        faction.id,
                    )

                for session_backup in cb.sessions:
                    session_note = SessionNote(
                        campaign_id=campaign.id,
                        date=session_backup.date,
                        title=session_backup.title,
                        content=session_backup.description,
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
                    refresh_reference_tags_for_resource(
                        db,
                        campaign.id,
                        ResourceType.SESSION,
                        session_note.id,
                    )

                    for roll in session_backup.rolls:
                        db.add(
                            RollEntry(
                                session_id=session_note.id,
                                roll=roll,
                            )
                        )

                for character_backup in cb.characters:
                    person_id = person_id_map.get(
                        character_backup.person_backup_id
                    )
                    if person_id is None:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Character profile references a missing "
                                "backup person"
                            ),
                        )

                    profile = CharacterProfile(
                        person_id=person_id,
                        short_bio=character_backup.short_bio,
                        appearance=character_backup.appearance,
                        image_path="",
                    )

                    if character_backup.image_archive_path:
                        original_path = Path(
                            character_backup.image_archive_path
                        )
                        image_data = read_archive_member(
                            archive, character_backup.image_archive_path
                        )
                        profile.image_path = write_image_from_bytes(
                            campaign.id,
                            original_path.suffix.lower(),
                            image_data,
                        )
                        saved_asset_paths.append(profile.image_path)

                    db.add(profile)
                    db.flush()

                    note_groups = [
                        (
                            CharacterNote,
                            ResourceType.CHARACTER_NOTE,
                            list(character_backup.notes),
                        ),
                        (
                            BackstoryNote,
                            ResourceType.BACKSTORY_NOTE,
                            list(character_backup.backstory_notes),
                        ),
                    ]
                    for legacy_entry in character_backup.entries:
                        legacy_type = legacy_entry.entry_type.casefold()
                        if legacy_type == "note":
                            note_groups[0][2].append(legacy_entry)
                        elif legacy_type == "backstory":
                            note_groups[1][2].append(legacy_entry)
                        else:
                            raise HTTPException(
                                status_code=400,
                                detail="Unknown character entry type in backup",
                            )

                    for note_model, resource_type, note_backups in note_groups:
                        for note_backup in note_backups:
                            note = note_model(
                                campaign_id=campaign.id,
                                character_person_id=person_id,
                                title=note_backup.title,
                                content=note_backup.content,
                                created_at=note_backup.created_at,
                                updated_at=note_backup.updated_at,
                            )
                            db.add(note)
                            db.flush()
                            sync_resource_tags(
                                db,
                                campaign.id,
                                resource_type,
                                note.id,
                                note_backup.tags,
                            )
                            refresh_reference_tags_for_resource(
                                db,
                                campaign.id,
                                resource_type,
                                note.id,
                            )

                active_backup_id = (
                    cb.campaign.active_character_person_backup_id
                )
                if active_backup_id is not None:
                    active_person_id = person_id_map.get(active_backup_id)
                    if (
                        active_person_id is None
                        or db.get(CharacterProfile, active_person_id) is None
                    ):
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Active character references a missing "
                                "character profile"
                            ),
                        )
                    campaign.active_character_person_id = active_person_id
                    db.add(campaign)

                if cb.inventories:
                    restore_inventory_backups(
                        campaign,
                        cb.inventories,
                        default_inventory,
                        person_id_map,
                        db,
                    )
                else:
                    sync_default_inventory_owner(campaign, db)

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

