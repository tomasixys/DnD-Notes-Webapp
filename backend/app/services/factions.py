from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import select

from app.models.api import (
    CampaignBackupFaction,
    FactionData,
    FactionRead,
)
from app.models.database import Faction
from app.models.enums import RelationshipType, ResourceType
from app.services.campaign_context import CampaignContext
from app.tags import (
    get_resource_relationship,
    get_resource_tag_reads,
    get_resource_tags,
    get_resources_referencing_tag,
    handle_tags_of_deleted_resource,
    refresh_reference_tags_for_resource,
    sync_resource_relationship,
    sync_resource_tags,
)


class FactionService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    def to_read(self, faction: Faction) -> FactionRead:
        return FactionRead(
            id=faction.id,
            campaign_id=faction.campaign_id,
            name=faction.name,
            type=faction.type,
            location=get_resource_relationship(
                self.db,
                ResourceType.FACTION,
                faction.id,
                RelationshipType.BASED_IN,
            ),
            members=get_resources_referencing_tag(
                self.db,
                self.context.campaign_id,
                ResourceType.FACTION,
                faction.id,
                ResourceType.PERSON,
                RelationshipType.MEMBER_OF,
            ),
            description=faction.description,
            tags=get_resource_tag_reads(
                self.db,
                ResourceType.FACTION,
                faction.id,
            ),
        )

    def get(self, faction_id: int) -> Faction:
        faction = self.db.get(Faction, faction_id)
        if (
            faction is None
            or faction.campaign_id != self.context.campaign_id
        ):
            raise HTTPException(status_code=404, detail="Faction not found")
        return faction

    def list(self) -> list[Faction]:
        statement = (
            select(Faction)
            .where(Faction.campaign_id == self.context.campaign_id)
            .order_by(Faction.name)
        )
        return self.db.exec(statement).all()

    def _stage_insert(
        self,
        *,
        name: str,
        faction_type: str,
        description: str,
        location: str,
        tags: list[str],
    ) -> Faction:
        faction = Faction(
            campaign_id=self.context.campaign_id,
            name=name,
            type=faction_type,
            description=description,
        )
        self.db.add(faction)
        self.db.flush()
        sync_resource_tags(
            self.db,
            self.context.campaign_id,
            ResourceType.FACTION,
            faction.id,
            tags,
        )
        sync_resource_relationship(
            self.db,
            self.context.campaign_id,
            ResourceType.FACTION,
            faction.id,
            RelationshipType.BASED_IN,
            ResourceType.LOCATION,
            location,
        )
        refresh_reference_tags_for_resource(
            self.db,
            self.context.campaign_id,
            ResourceType.FACTION,
            faction.id,
        )
        return faction

    def stage_create(self, faction_data: FactionData) -> Faction:
        return self._stage_insert(
            name=faction_data.name,
            faction_type=faction_data.type,
            description=faction_data.description,
            location=faction_data.location,
            tags=faction_data.tags,
        )

    def create(self, faction_data: FactionData) -> FactionRead:
        try:
            faction = self.stage_create(faction_data)
            self.db.commit()
            self.db.refresh(faction)
            return self.to_read(faction)
        except Exception:
            self.db.rollback()
            raise

    def stage_update(
        self,
        faction_id: int,
        faction_data: FactionData,
    ) -> Faction:
        faction = self.get(faction_id)
        previous_name = faction.name
        faction.name = faction_data.name
        faction.type = faction_data.type
        faction.description = faction_data.description
        self.db.add(faction)
        self.db.flush()
        sync_resource_tags(
            self.db,
            self.context.campaign_id,
            ResourceType.FACTION,
            faction.id,
            faction_data.tags,
        )
        sync_resource_relationship(
            self.db,
            self.context.campaign_id,
            ResourceType.FACTION,
            faction.id,
            RelationshipType.BASED_IN,
            ResourceType.LOCATION,
            faction_data.location,
        )
        refresh_reference_tags_for_resource(
            self.db,
            self.context.campaign_id,
            ResourceType.FACTION,
            faction.id,
            previous_labels=[previous_name],
        )
        return faction

    def update(
        self,
        faction_id: int,
        faction_data: FactionData,
    ) -> FactionRead:
        try:
            faction = self.stage_update(faction_id, faction_data)
            self.db.commit()
            self.db.refresh(faction)
            return self.to_read(faction)
        except Exception:
            self.db.rollback()
            raise

    def stage_delete(self, faction_id: int) -> None:
        faction = self.get(faction_id)
        handle_tags_of_deleted_resource(
            self.db,
            ResourceType.FACTION,
            faction.id,
        )
        self.db.delete(faction)
        self.db.flush()

    def delete(self, faction_id: int) -> None:
        try:
            self.stage_delete(faction_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def to_backup(self, faction: Faction) -> CampaignBackupFaction:
        relationship = get_resource_relationship(
            self.db,
            ResourceType.FACTION,
            faction.id,
            RelationshipType.BASED_IN,
        )
        return CampaignBackupFaction(
            name=faction.name,
            type=faction.type,
            location=relationship.label if relationship else "",
            description=faction.description,
            tags=get_resource_tags(
                self.db,
                ResourceType.FACTION,
                faction.id,
            ),
        )

    def stage_restore(
        self,
        faction_backup: CampaignBackupFaction,
    ) -> Faction:
        return self._stage_insert(
            name=faction_backup.name,
            faction_type=faction_backup.type,
            description=faction_backup.description,
            location=faction_backup.location,
            tags=faction_backup.tags,
        )
