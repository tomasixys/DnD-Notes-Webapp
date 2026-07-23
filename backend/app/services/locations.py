from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import select

from app.models.api import (
    CampaignBackupLocation,
    DeleteResponse,
    LocationData,
    LocationRead,
)
from app.models.database import Location
from app.models.enums import RelationshipType, ResourceType
from app.services.campaign_context import CampaignContext
from app.services.tags import TagService


class LocationService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db
        self.tags = TagService(context)

    def to_read(self, location: Location) -> LocationRead:
        return LocationRead(
            id=location.id,
            campaign_id=location.campaign_id,
            name=location.name,
            type=location.type,
            parent_location=self.tags.get_relationship(
                ResourceType.LOCATION,
                location.id,
                RelationshipType.PART_OF,
            ),
            people=self.tags.list_referencing_resources(
                target_type=ResourceType.LOCATION,
                target_id=location.id,
                owner_type=ResourceType.PERSON,
                relationship_type=RelationshipType.LOCATED_IN,
            ),
            description=location.description,
            tags=self.tags.list_tag_reads(
                ResourceType.LOCATION,
                location.id,
            ),
        )

    def get(self, location_id: int) -> Location:
        location = self.db.get(Location, location_id)
        if (
            location is None
            or location.campaign_id != self.context.campaign_id
        ):
            raise HTTPException(status_code=404, detail="Location not found")
        return location

    def list(self) -> list[Location]:
        statement = (
            select(Location)
            .where(Location.campaign_id == self.context.campaign_id)
            .order_by(func.lower(Location.name), Location.id)
        )
        return self.db.exec(statement).all()

    def _sync_parent(
        self,
        location_id: int,
        parent_location: str,
    ) -> None:
        try:
            self.tags.stage_sync_relationship(
                ResourceType.LOCATION,
                location_id,
                RelationshipType.PART_OF,
                ResourceType.LOCATION,
                parent_location,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    def _stage_insert(
        self,
        *,
        name: str,
        location_type: str,
        description: str,
        parent_location: str,
        tags: list[str],
    ) -> Location:
        location = Location(
            campaign_id=self.context.campaign_id,
            name=name,
            type=location_type,
            description=description,
        )
        self.db.add(location)
        self.db.flush()
        self.tags.stage_sync_tags(
            ResourceType.LOCATION,
            location.id,
            tags,
        )
        self._sync_parent(location.id, parent_location)
        self.tags.stage_refresh_references(
            ResourceType.LOCATION,
            location.id,
        )
        return location

    def stage_create(self, location_data: LocationData) -> Location:
        return self._stage_insert(
            name=location_data.name,
            location_type=location_data.type,
            description=location_data.description,
            parent_location=location_data.parent_location,
            tags=location_data.tags,
        )

    def create(self, location_data: LocationData) -> LocationRead:
        try:
            location = self.stage_create(location_data)
            self.db.commit()
            self.db.refresh(location)
            return self.to_read(location)
        except Exception:
            self.db.rollback()
            raise

    def stage_update(
        self,
        location_id: int,
        location_data: LocationData,
    ) -> Location:
        location = self.get(location_id)
        previous_name = location.name
        location.name = location_data.name
        location.type = location_data.type
        location.description = location_data.description
        self.db.add(location)
        self.db.flush()
        self.tags.stage_sync_tags(
            ResourceType.LOCATION,
            location.id,
            location_data.tags,
        )
        self._sync_parent(location.id, location_data.parent_location)
        self.tags.stage_refresh_references(
            ResourceType.LOCATION,
            location.id,
            previous_labels=[previous_name],
        )
        return location

    def update(
        self,
        location_id: int,
        location_data: LocationData,
    ) -> LocationRead:
        try:
            location = self.stage_update(location_id, location_data)
            self.db.commit()
            self.db.refresh(location)
            return self.to_read(location)
        except Exception:
            self.db.rollback()
            raise

    def stage_delete(self, location_id: int) -> None:
        location = self.get(location_id)
        self.tags.stage_handle_resource_deletion(
            ResourceType.LOCATION,
            location.id,
        )
        self.db.delete(location)
        self.db.flush()

    def delete(self, location_id: int) -> DeleteResponse:
        try:
            self.stage_delete(location_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return DeleteResponse(deleted_id=location_id)

    def to_backup(self, location: Location) -> CampaignBackupLocation:
        relationship = self.tags.get_relationship(
            ResourceType.LOCATION,
            location.id,
            RelationshipType.PART_OF,
        )
        return CampaignBackupLocation(
            name=location.name,
            type=location.type,
            parent_location=relationship.label if relationship else "",
            description=location.description,
            tags=self.tags.list_values(
                ResourceType.LOCATION,
                location.id,
            ),
        )

    def list_backup_entries(self) -> list[CampaignBackupLocation]:
        locations = sorted(
            self.list(),
            key=lambda location: (
                location.name.lower(),
                location.id or 0,
            ),
        )
        return [self.to_backup(location) for location in locations]

    def stage_restore(
        self,
        location_backup: CampaignBackupLocation,
    ) -> Location:
        return self._stage_insert(
            name=location_backup.name,
            location_type=location_backup.type,
            description=location_backup.description,
            parent_location=location_backup.parent_location,
            tags=location_backup.tags,
        )
