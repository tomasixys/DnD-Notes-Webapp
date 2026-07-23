from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import select

from app.models.api import (
    CampaignBackupLocation,
    LocationData,
    LocationRead,
)
from app.models.database import Location
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


class LocationService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    def to_read(self, location: Location) -> LocationRead:
        return LocationRead(
            id=location.id,
            campaign_id=location.campaign_id,
            name=location.name,
            type=location.type,
            parent_location=get_resource_relationship(
                self.db,
                ResourceType.LOCATION,
                location.id,
                RelationshipType.PART_OF,
            ),
            people=get_resources_referencing_tag(
                self.db,
                self.context.campaign_id,
                ResourceType.LOCATION,
                location.id,
                ResourceType.PERSON,
                RelationshipType.LOCATED_IN,
            ),
            description=location.description,
            tags=get_resource_tag_reads(
                self.db,
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
            .order_by(Location.name)
        )
        return self.db.exec(statement).all()

    def _sync_parent(
        self,
        location_id: int,
        parent_location: str,
    ) -> None:
        try:
            sync_resource_relationship(
                self.db,
                self.context.campaign_id,
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
        sync_resource_tags(
            self.db,
            self.context.campaign_id,
            ResourceType.LOCATION,
            location.id,
            tags,
        )
        self._sync_parent(location.id, parent_location)
        refresh_reference_tags_for_resource(
            self.db,
            self.context.campaign_id,
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
        sync_resource_tags(
            self.db,
            self.context.campaign_id,
            ResourceType.LOCATION,
            location.id,
            location_data.tags,
        )
        self._sync_parent(location.id, location_data.parent_location)
        refresh_reference_tags_for_resource(
            self.db,
            self.context.campaign_id,
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
        handle_tags_of_deleted_resource(
            self.db,
            ResourceType.LOCATION,
            location.id,
        )
        self.db.delete(location)
        self.db.flush()

    def delete(self, location_id: int) -> None:
        try:
            self.stage_delete(location_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def to_backup(self, location: Location) -> CampaignBackupLocation:
        relationship = get_resource_relationship(
            self.db,
            ResourceType.LOCATION,
            location.id,
            RelationshipType.PART_OF,
        )
        return CampaignBackupLocation(
            name=location.name,
            type=location.type,
            parent_location=relationship.label if relationship else "",
            description=location.description,
            tags=get_resource_tags(
                self.db,
                ResourceType.LOCATION,
                location.id,
            ),
        )

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
