from collections.abc import Iterable

from fastapi import HTTPException

from app.authorization.enums import CampaignCapability
from app.authorization.resource_policy import (
    PROTECTED_NOTE_DEFINITIONS,
    ResourceAccessPolicy,
)
from app.models.api import ResourceTagRead
from app.models.enums import RelationshipType, ResourceType
from app.authorization.context import CampaignContext
from app.tags import (
    REFERENCE_MODELS,
    get_resource_relationship,
    get_resource_tag_reads,
    get_resource_tags,
    get_resources_referencing_tag,
    get_tag_matching_owner_ids,
    get_tag_matching_owner_rows,
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
        self.policy = ResourceAccessPolicy(context)

    def _verify_owner(
        self,
        owner_type: ResourceType,
        owner_id: int,
        *,
        write: bool = False,
    ) -> None:
        self.context.require(CampaignCapability.SHARED_RESOURCE_READ)
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
        definition = PROTECTED_NOTE_DEFINITIONS.get(owner_type)
        if definition is not None:
            _, grant_model = definition
            if write:
                self.policy.require_write(
                    resource,
                    grant_model,
                    detail="Tag owner not found",
                )
            else:
                self.policy.require_read(
                    resource,
                    grant_model,
                    detail="Tag owner not found",
                )

    def _filter_tag_reads(
        self,
        tags: list[ResourceTagRead],
    ) -> list[ResourceTagRead]:
        return [
            tag
            for tag in tags
            if (
                tag.reference_type is None
                or tag.reference_id is None
                or self.policy.can_read_reference(
                    tag.reference_type,
                    tag.reference_id,
                )
            )
        ]

    def list_values(
        self,
        owner_type: ResourceType,
        owner_id: int,
    ) -> list[str]:
        self._verify_owner(owner_type, owner_id)
        return [
            tag.value
            for tag in self.list_tag_reads(owner_type, owner_id)
        ]

    def list_tag_reads(
        self,
        owner_type: ResourceType,
        owner_id: int,
    ) -> list[ResourceTagRead]:
        self._verify_owner(owner_type, owner_id)
        return self._filter_tag_reads(
            get_resource_tag_reads(
                self.db,
                owner_type,
                owner_id,
            )
        )

    def get_relationship(
        self,
        owner_type: ResourceType,
        owner_id: int,
        relationship_type: RelationshipType,
    ) -> ResourceTagRead | None:
        self._verify_owner(owner_type, owner_id)
        relationship = get_resource_relationship(
            self.db,
            owner_type,
            owner_id,
            relationship_type,
        )
        if relationship is None:
            return None
        filtered = self._filter_tag_reads([relationship])
        return filtered[0] if filtered else None

    def list_referencing_resources(
        self,
        *,
        target_type: ResourceType,
        target_id: int,
        owner_type: ResourceType,
        relationship_type: RelationshipType,
    ) -> list[ResourceTagRead]:
        self._verify_owner(target_type, target_id)
        references = get_resources_referencing_tag(
            self.db,
            self.context.campaign_id,
            target_type,
            target_id,
            owner_type,
            relationship_type,
        )
        return self._filter_tag_reads(references)

    def find_matching_owner_ids(
        self,
        owner_type: ResourceType,
        pattern: str,
    ) -> list[int]:
        self.context.require(CampaignCapability.SHARED_RESOURCE_READ)
        rows = get_tag_matching_owner_rows(
            self.db,
            self.context.campaign_id,
            owner_type,
            pattern,
        )
        readable_owner_ids = self.policy.filter_readable_ids(
            owner_type,
            [owner_id for owner_id, _ in rows],
        )
        readable_owner_id_set = set(readable_owner_ids)
        return list(
            dict.fromkeys(
                owner_id
                for owner_id, tag in rows
                if owner_id in readable_owner_id_set
                and (
                    tag.reference_type is None
                    or tag.reference_id is None
                    or self.policy.can_read_reference(
                        ResourceType(tag.reference_type),
                        tag.reference_id,
                    )
                )
            )
        )

    def stage_sync_tags(
        self,
        owner_type: ResourceType,
        owner_id: int,
        raw_tags: Iterable[str],
    ) -> None:
        self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        self._verify_owner(owner_type, owner_id, write=True)
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
        self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        self._verify_owner(owner_type, owner_id, write=True)
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
        self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        self._verify_owner(resource_type, resource_id, write=True)
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
        self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        self._verify_owner(owner_type, owner_id, write=True)
        handle_tags_of_deleted_resource(
            self.db,
            owner_type,
            owner_id,
        )
