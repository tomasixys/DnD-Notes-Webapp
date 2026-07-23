import io
import json
from pathlib import Path
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import SQLModel, Session

from app.file_storage import (
    add_upload_to_archive,
    build_upload_url,
    delete_uploaded_file,
    get_uploaded_file_path,
    make_backup_archive_path,
    read_archive_member,
    write_image_from_bytes,
)
from app.models.api import (
    CAMPAIGN_BACKUP_SCHEMA_VERSION,
    CampaignBackup,
    CampaignBackupCampaign,
    CampaignBackupCharacter,
    CampaignBackupExportRead,
    CampaignRead,
    PersonData,
)
from app.models.database import Campaign
from app.services.campaign_context import CampaignContext
from app.services.campaigns import CampaignService
from app.services.character_notes import (
    BackstoryNoteService,
    CharacterNoteService,
)
from app.services.characters import CharacterService
from app.services.factions import FactionService
from app.services.inventory import InventoryService
from app.services.locations import LocationService
from app.services.people import PersonService
from app.services.sessions import SessionNoteService


def _sqlmodel_to_dict(model: SQLModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


class CampaignBackupService:
    def __init__(self, db: Session):
        self.db = db
        self.campaigns = CampaignService(db)

    def export(self, campaign_id: int) -> CampaignBackupExportRead:
        context = CampaignContext.resolve(self.db, campaign_id)
        campaign = context.campaign
        people = PersonService(context)
        inventory = InventoryService(context)
        characters = CharacterService(
            context,
            people=people,
            inventory=inventory,
        )
        sessions = SessionNoteService(context)
        locations = LocationService(context)
        factions = FactionService(context)

        archive_path, relative_path = make_backup_archive_path(
            campaign.name
        )
        character_image_archive_paths: dict[int, str] = {}

        try:
            with ZipFile(
                archive_path,
                "w",
                compression=ZIP_DEFLATED,
            ) as archive:
                image_archive_path = (
                    add_upload_to_archive(
                        archive,
                        campaign.image_path,
                        "assets/campaign-image"
                        + self._uploaded_suffix(campaign.image_path),
                    )
                    if campaign.image_path
                    else ""
                )
                banner_archive_path = (
                    add_upload_to_archive(
                        archive,
                        campaign.banner_image_path,
                        "assets/campaign-banner"
                        + self._uploaded_suffix(
                            campaign.banner_image_path
                        ),
                    )
                    if campaign.banner_image_path
                    else ""
                )

                for profile in characters.list_profiles_for_backup():
                    if not profile.image_path:
                        continue
                    suffix = self._uploaded_suffix(profile.image_path)
                    archive_member = add_upload_to_archive(
                        archive,
                        profile.image_path,
                        (
                            "assets/characters/"
                            f"{profile.person_id}-portrait{suffix}"
                        ),
                    )
                    if archive_member:
                        character_image_archive_paths[
                            profile.person_id
                        ] = archive_member

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
                    sessions=sessions.list_backup_entries(),
                    people=people.list_backup_entries(),
                    characters=characters.list_backup_entries(
                        character_image_archive_paths
                    ),
                    locations=locations.list_backup_entries(),
                    factions=factions.list_backup_entries(),
                    inventories=inventory.list_backup_entries(),
                )
                archive.writestr(
                    "backup.json",
                    json.dumps(
                        _sqlmodel_to_dict(backup),
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise

        return CampaignBackupExportRead(
            backup_url=build_upload_url(relative_path),
            filename=archive_path.name,
        )

    def import_archive(self, raw_data: bytes) -> CampaignRead:
        try:
            with ZipFile(io.BytesIO(raw_data), "r") as archive:
                backup = self._read_backup(archive)
                campaign = self._restore(archive, backup)
        except BadZipFile:
            raise HTTPException(
                status_code=400,
                detail="Invalid backup archive",
            )
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail="Backup archive is missing backup.json",
            )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid backup JSON",
            )
        except (UnicodeDecodeError, ValidationError):
            raise HTTPException(
                status_code=400,
                detail="Invalid backup data",
            )

        return self.campaigns.to_read(
            campaign,
            session_count=len(backup.sessions),
        )

    @staticmethod
    def _uploaded_suffix(relative_path: str) -> str:
        source_path = get_uploaded_file_path(relative_path)
        if source_path is None or not source_path.exists():
            return ""
        return source_path.suffix.lower()

    @staticmethod
    def _read_backup(archive: ZipFile) -> CampaignBackup:
        parsed_json = json.loads(
            archive.read("backup.json").decode("utf-8")
        )
        backup = CampaignBackup(**parsed_json)
        if not (
            1
            <= backup.schema_version
            <= CAMPAIGN_BACKUP_SCHEMA_VERSION
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported backup schema version: "
                    f"{backup.schema_version}"
                ),
            )
        return backup

    def _restore(
        self,
        archive: ZipFile,
        backup: CampaignBackup,
    ) -> Campaign:
        saved_asset_paths: list[str] = []
        person_id_map: dict[int, int] = {}

        try:
            campaign = self.campaigns.stage_create(
                name=backup.campaign.name,
                player_character=backup.campaign.player_character,
                description=backup.campaign.description,
            )
            context = CampaignContext(self.db, campaign)
            inventory = InventoryService(context)

            campaign.image_path = self._restore_asset(
                archive,
                campaign.id,
                backup.campaign.image_archive_path,
                saved_asset_paths,
            )
            campaign.banner_image_path = self._restore_asset(
                archive,
                campaign.id,
                backup.campaign.banner_archive_path,
                saved_asset_paths,
            )
            self.db.add(campaign)

            people = PersonService(context)
            characters = CharacterService(
                context,
                people=people,
                inventory=inventory,
            )
            character_notes = CharacterNoteService(
                context,
                characters,
            )
            backstory_notes = BackstoryNoteService(
                context,
                characters,
            )
            sessions = SessionNoteService(context)
            locations = LocationService(context)
            factions = FactionService(context)

            for person_backup in backup.people:
                person = people.stage_create(
                    PersonData(
                        name=person_backup.name,
                        role=person_backup.role,
                        faction=person_backup.faction,
                        location=person_backup.location,
                        description=person_backup.description,
                        tags=person_backup.tags,
                    )
                )
                if person_backup.backup_id is not None:
                    person_id_map[person_backup.backup_id] = person.id

            for location_backup in backup.locations:
                locations.stage_restore(location_backup)
            for faction_backup in backup.factions:
                factions.stage_restore(faction_backup)
            for session_backup in backup.sessions:
                sessions.stage_restore(session_backup)

            for character_backup in backup.characters:
                self._restore_character(
                    archive,
                    campaign.id,
                    character_backup,
                    person_id_map,
                    saved_asset_paths,
                    characters,
                    character_notes,
                    backstory_notes,
                )

            self._restore_active_character(
                backup,
                person_id_map,
                characters,
            )

            if backup.inventories:
                inventory.stage_restore_backups(
                    backup.inventories,
                    person_id_map,
                )
            else:
                inventory.stage_sync_default_owner()

            self.db.commit()
            self.db.refresh(campaign)
            return campaign
        except Exception:
            self.db.rollback()
            for asset_path in saved_asset_paths:
                delete_uploaded_file(asset_path)
            raise

    @staticmethod
    def _restore_asset(
        archive: ZipFile,
        campaign_id: int,
        archive_path: str,
        saved_asset_paths: list[str],
    ) -> str:
        if not archive_path:
            return ""
        suffix = Path(archive_path).suffix.lower()
        image_data = read_archive_member(archive, archive_path)
        saved_path = write_image_from_bytes(
            campaign_id,
            suffix,
            image_data,
        )
        saved_asset_paths.append(saved_path)
        return saved_path

    def _restore_character(
        self,
        archive: ZipFile,
        campaign_id: int,
        character_backup: CampaignBackupCharacter,
        person_id_map: dict[int, int],
        saved_asset_paths: list[str],
        characters: CharacterService,
        character_notes: CharacterNoteService,
        backstory_notes: BackstoryNoteService,
    ) -> None:
        person_id = person_id_map.get(
            character_backup.person_backup_id
        )
        if person_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Character profile references a missing backup person"
                ),
            )

        image_path = self._restore_asset(
            archive,
            campaign_id,
            character_backup.image_archive_path,
            saved_asset_paths,
        )
        characters.stage_create_profile(
            person_id,
            short_bio=character_backup.short_bio,
            appearance=character_backup.appearance,
            image_path=image_path,
        )

        note_groups = [
            (character_notes, list(character_backup.notes)),
            (backstory_notes, list(character_backup.backstory_notes)),
        ]
        for legacy_entry in character_backup.entries:
            legacy_type = legacy_entry.entry_type.casefold()
            if legacy_type == "note":
                note_groups[0][1].append(legacy_entry)
            elif legacy_type == "backstory":
                note_groups[1][1].append(legacy_entry)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Unknown character entry type in backup",
                )

        for note_service, note_backups in note_groups:
            for note_backup in note_backups:
                note_service.stage_restore(person_id, note_backup)

    @staticmethod
    def _restore_active_character(
        backup: CampaignBackup,
        person_id_map: dict[int, int],
        characters: CharacterService,
    ) -> None:
        active_backup_id = (
            backup.campaign.active_character_person_backup_id
        )
        if active_backup_id is None:
            return

        active_person_id = person_id_map.get(active_backup_id)
        if active_person_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Active character references a missing character profile"
                ),
            )
        try:
            characters.set_active_pointer(active_person_id)
        except HTTPException as error:
            if error.status_code != 404:
                raise
            raise HTTPException(
                status_code=400,
                detail=(
                    "Active character references a missing character profile"
                ),
            ) from error
