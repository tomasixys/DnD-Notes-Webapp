"""Read assigned tags, relationships, reverse links, and search matches."""

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models.api import ResourceTagRead
from app.models.database import Tag, TagAssignment
from app.models.enums import RelationshipType, ResourceType, TagResolutionState

from .references import canonical_label, resource_model
from .syntax import format_tag


def _to_tag_read(
    tag: Tag,
    relationship_type: str | None,
) -> ResourceTagRead:
    return ResourceTagRead(
        value=format_tag(tag),
        label=tag.label,
        reference_type=(
            ResourceType(tag.reference_type)
            if tag.reference_type
            else None
        ),
        reference_id=tag.reference_id,
        relationship_type=(
            RelationshipType(relationship_type)
            if relationship_type
            else None
        ),
        resolution_state=TagResolutionState(tag.resolution_state),
    )


def get_resource_tags(
    db: Session,
    owner_type: ResourceType,
    owner_id: int,
) -> list[str]:
    statement = (
        select(Tag)
        .join(TagAssignment, TagAssignment.tag_id == Tag.id)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(TagAssignment.owner_id == owner_id)
        .where(
            TagAssignment.relationship_type
            == RelationshipType.ASSOCIATED_WITH.value
        )
        .order_by(Tag.reference_type, Tag.normalized_label, Tag.id)
    )
    return [format_tag(tag) for tag in db.exec(statement).all()]


def _get_statement_tag_of_relationship_type(relationship_type: RelationshipType, owner_type: ResourceType, owner_id: int):
    return (
        select(Tag, TagAssignment.relationship_type)
        .join(TagAssignment, TagAssignment.tag_id == Tag.id)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(TagAssignment.owner_id == owner_id)
        .where(TagAssignment.relationship_type == relationship_type.value)
    )

def get_resource_tag_reads(
    db: Session,
    owner_type: ResourceType,
    owner_id: int,
) -> list[ResourceTagRead]:
    statement = _get_statement_tag_of_relationship_type(
        RelationshipType.ASSOCIATED_WITH, owner_type, owner_id
        ).order_by(Tag.reference_type, Tag.normalized_label, Tag.id)
    return [ _to_tag_read(tag, relationship_type)
        for tag, relationship_type in db.exec(statement).all()
    ]


def get_resource_relationship(
    db: Session,
    owner_type: ResourceType,
    owner_id: int,
    relationship_type: RelationshipType,
) -> ResourceTagRead | None:
    statement = _get_statement_tag_of_relationship_type(
        relationship_type, owner_type, owner_id
    ).order_by(Tag.id)

    if (row := db.exec(statement).first()) is None:
        return None

    tag, stored_relationship_type = row
    return _to_tag_read(tag, stored_relationship_type)


def get_resources_referencing_tag(
    db: Session,
    campaign_id: int,
    target_type: ResourceType,
    target_id: int,
    owner_type: ResourceType,
    relationship_type: RelationshipType,
) -> list[ResourceTagRead]:
    model = resource_model(owner_type)
    statement = (
        select(model)
        .join(
            TagAssignment,
            and_(
                TagAssignment.owner_type == owner_type.value,
                TagAssignment.owner_id == model.id,
            ),
        )
        .join(Tag, Tag.id == TagAssignment.tag_id)
        .where(model.campaign_id == campaign_id)
        .where(Tag.reference_type == target_type.value)
        .where(Tag.reference_id == target_id)
        .where(TagAssignment.relationship_type == relationship_type.value)
        .order_by(model.name)
    )

    return [
        ResourceTagRead(
            value=f"{owner_type.value}:{canonical_label(owner_type, owner)}",
            label=canonical_label(owner_type, owner),
            reference_type=owner_type,
            reference_id=owner.id,
            relationship_type=relationship_type,
            resolution_state=TagResolutionState.RESOLVED,
        )
        for owner in db.exec(statement).all()
    ]


def get_tag_matching_owner_ids(
    db: Session,
    campaign_id: int,
    owner_type: ResourceType,
    pattern: str,
) -> list[int]:
    statement = (
        select(TagAssignment.owner_id)
        .join(Tag, Tag.id == TagAssignment.tag_id)
        .where(Tag.campaign_id == campaign_id)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(
            or_(
                Tag.label.ilike(pattern, escape="\\"),
                Tag.reference_type.ilike(pattern, escape="\\"),
            )
        )
        .distinct()
    )
    return list(db.exec(statement).all())
