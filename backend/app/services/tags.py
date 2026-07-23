from collections.abc import Iterable

from fastapi import HTTPException

from app.models.api import ResourceTagRead
from app.models.enums import RelationshipType, ResourceType
from app.services.campaign_context import CampaignContext
from app.tags import (
    REFERENCE_MODELS,
    get_resource_relationship,
    get_resource_tag_reads,
    get_resource_tags,
    get_resources_referencing_tag,
    get_tag_matching_owner_ids,
    handle_tags_of_deleted_resource,
    refresh_reference_tags_for_resource,
    sync_resource_relationship,
    sync_resource_tags,
)


class TagService:
    """Campaign-scoped tag, reference, and relationship operations."""

    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    def _verify_owner(
        self,
        owner_type: ResourceType,
        owner_id: int,
    ) -> None:
        resource = self.db.get(
            REFERENCE_MODELS[owner_type],
            owner_id,
        )
        if (
            resource is None
            or resource.campaign_id != self.context.campaign_id
        ):
            raise HTTPException(
                status_code=404,
                detail="Tag owner not found",
            )

    def list_values(
        self,
        owner_type: ResourceType,
        owner_id: int,
    ) -> list[str]:
        self._verify_owner(owner_type, owner_id)
        return get_resource_tags(
            self.db,
            owner_type,
            owner_id,
        )

    def list_tag_reads(
        self,
        owner_type: ResourceType,
        owner_id: int,
    ) -> list[ResourceTagRead]:
        self._verify_owner(owner_type, owner_id)
        return get_resource_tag_reads(
            self.db,
            owner_type,
            owner_id,
        )

    def get_relationship(
        self,
        owner_type: ResourceType,
        owner_id: int,
        relationship_type: RelationshipType,
    ) -> ResourceTagRead | None:
        self._verify_owner(owner_type, owner_id)
        return get_resource_relationship(
            self.db,
            owner_type,
            owner_id,
            relationship_type,
        )

    def list_referencing_resources(
        self,
        *,
        target_type: ResourceType,
        target_id: int,
        owner_type: ResourceType,
        relationship_type: RelationshipType,
    ) -> list[ResourceTagRead]:
        self._verify_owner(target_type, target_id)
        return get_resources_referencing_tag(
            self.db,
            self.context.campaign_id,
            target_type,
            target_id,
            owner_type,
            relationship_type,
        )

    def find_matching_owner_ids(
        self,
        owner_type: ResourceType,
        pattern: str,
    ) -> list[int]:
        return get_tag_matching_owner_ids(
            self.db,
            self.context.campaign_id,
            owner_type,
            pattern,
        )

    def stage_sync_tags(
        self,
        owner_type: ResourceType,
        owner_id: int,
        raw_tags: Iterable[str],
    ) -> None:
        self._verify_owner(owner_type, owner_id)
        sync_resource_tags(
            self.db,
            self.context.campaign_id,
            owner_type,
            owner_id,
            raw_tags,
        )

    def stage_sync_relationship(
        self,
        owner_type: ResourceType,
        owner_id: int,
        relationship_type: RelationshipType,
        reference_type: ResourceType,
        raw_reference: str,
    ) -> None:
        self._verify_owner(owner_type, owner_id)
        sync_resource_relationship(
            self.db,
            self.context.campaign_id,
            owner_type,
            owner_id,
            relationship_type,
            reference_type,
            raw_reference,
        )

    def stage_refresh_references(
        self,
        resource_type: ResourceType,
        resource_id: int,
        previous_labels: Iterable[str] = (),
    ) -> None:
        self._verify_owner(resource_type, resource_id)
        refresh_reference_tags_for_resource(
            self.db,
            self.context.campaign_id,
            resource_type,
            resource_id,
            previous_labels,
        )

    def stage_handle_resource_deletion(
        self,
        owner_type: ResourceType,
        owner_id: int,
    ) -> None:
        self._verify_owner(owner_type, owner_id)
        handle_tags_of_deleted_resource(
            self.db,
            owner_type,
            owner_id,
        )
