"""Resolve tag references and keep their identities current over renames."""

from typing import Iterable

from sqlmodel import Session, select

from app.models.api import ParsedTag
from app.models.database import (
    Faction,
    Location,
    Person,
    SessionNote,
    Tag,
    TagAssignment,
)
from app.models.enums import ResourceType, TagResolutionState

from .syntax import normalize_tag_label, resolved_tag_key


REFERENCE_MODELS = {
    ResourceType.PERSON: Person,
    ResourceType.LOCATION: Location,
    ResourceType.FACTION: Faction,
    ResourceType.SESSION: SessionNote,
}


def resource_model(resource_type: ResourceType):
    return REFERENCE_MODELS[resource_type]


def candidate_labels(resource_type: ResourceType, resource) -> list[str]:
    if resource_type == ResourceType.SESSION:
        return [
            resource.title,
            str(resource.session_number),
            f"session {resource.session_number}",
        ]
    return [resource.name]


def canonical_label(resource_type: ResourceType, resource) -> str:
    if resource_type == ResourceType.SESSION:
        return resource.title
    return resource.name


def resolve_reference(
    db: Session,
    campaign_id: int,
    resource_type: ResourceType,
    label: str,
) -> tuple[int | None, TagResolutionState]:
    model = resource_model(resource_type)
    statement = select(model).where(model.campaign_id == campaign_id)
    resources = db.exec(statement).all()
    normalized_label = normalize_tag_label(label)

    matches = [
        resource
        for resource in resources
        if any(
            normalize_tag_label(candidate) == normalized_label
            for candidate in candidate_labels(resource_type, resource)
        )
    ]

    if len(matches) == 1:
        return matches[0].id, TagResolutionState.RESOLVED
    if len(matches) > 1:
        return None, TagResolutionState.AMBIGUOUS
    return None, TagResolutionState.UNRESOLVED


def get_or_create_tag_definition(
    db: Session,
    campaign_id: int,
    parsed: ParsedTag,
) -> Tag:
    reference_id: int | None = None
    state = TagResolutionState.PASSIVE
    key = parsed.key
    label = parsed.label

    if parsed.reference_type:
        reference_id, state = resolve_reference(
            db,
            campaign_id,
            parsed.reference_type,
            parsed.label,
        )
        if reference_id is not None:
            key = resolved_tag_key(parsed.reference_type, reference_id)
            resource = db.get(resource_model(parsed.reference_type), reference_id)
            if resource is not None:
                label = canonical_label(parsed.reference_type, resource)

    tag = db.exec(
        select(Tag)
        .where(Tag.campaign_id == campaign_id)
        .where(Tag.key == key)
    ).first()

    if tag is None:
        tag = Tag(
            campaign_id=campaign_id,
            label=label,
            normalized_label=normalize_tag_label(label),
            key=key,
            reference_type=(
                parsed.reference_type.value
                if parsed.reference_type
                else None
            ),
            reference_id=reference_id,
            resolution_state=state.value,
        )
    elif parsed.reference_type:
        tag.label = label
        tag.normalized_label = normalize_tag_label(label)
        tag.reference_id = reference_id
        tag.resolution_state = state.value
    else:
        tag.reference_id = None
        tag.resolution_state = TagResolutionState.PASSIVE.value

    db.add(tag)
    db.flush()
    return tag


def merge_tag_definitions(db: Session, source: Tag, destination: Tag) -> Tag:
    assignments = db.exec(
        select(TagAssignment).where(TagAssignment.tag_id == source.id)
    ).all()

    for assignment in assignments:
        existing_assignment = db.exec(
            select(TagAssignment)
            .where(TagAssignment.tag_id == destination.id)
            .where(TagAssignment.owner_type == assignment.owner_type)
            .where(TagAssignment.owner_id == assignment.owner_id)
            .where(
                TagAssignment.relationship_type
                == assignment.relationship_type
            )
        ).first()
        if existing_assignment is None:
            assignment.tag_id = destination.id
            db.add(assignment)
        else:
            db.delete(assignment)

    db.flush()
    db.delete(source)
    db.flush()
    return destination


def promote_tag_reference(
    db: Session,
    tag: Tag,
    resource_type: ResourceType,
    reference_id: int,
) -> Tag:
    resource = db.get(resource_model(resource_type), reference_id)
    if resource is None:
        return tag

    key = resolved_tag_key(resource_type, reference_id)
    canonical = canonical_label(resource_type, resource)
    identity_tag = db.exec(
        select(Tag)
        .where(Tag.campaign_id == tag.campaign_id)
        .where(Tag.key == key)
    ).first()

    if identity_tag is not None and identity_tag.id != tag.id:
        tag = merge_tag_definitions(db, tag, identity_tag)

    tag.key = key
    tag.label = canonical
    tag.normalized_label = normalize_tag_label(canonical)
    tag.reference_id = reference_id
    tag.resolution_state = TagResolutionState.RESOLVED.value
    db.add(tag)
    db.flush()
    return tag


def resolve_pending_tags_for_resource(
    db: Session,
    campaign_id: int,
    resource_type: ResourceType,
    label: str,
) -> None:
    normalized_label = normalize_tag_label(label)
    tags = db.exec(
        select(Tag)
        .where(Tag.campaign_id == campaign_id)
        .where(Tag.reference_type == resource_type.value)
        .where(Tag.normalized_label == normalized_label)
        .where(Tag.reference_id.is_(None))
    ).all()

    for tag in tags:
        reference_id, state = resolve_reference(
            db,
            campaign_id,
            resource_type,
            tag.label,
        )
        if reference_id is not None:
            promote_tag_reference(db, tag, resource_type, reference_id)
        else:
            tag.reference_id = None
            tag.resolution_state = state.value
            db.add(tag)


def refresh_reference_tags_for_resource(
    db: Session,
    campaign_id: int,
    resource_type: ResourceType,
    resource_id: int,
    previous_labels: Iterable[str] = (),
) -> None:
    resource = db.get(resource_model(resource_type), resource_id)
    if resource is None or resource.campaign_id != campaign_id:
        return

    linked_tags = db.exec(
        select(Tag)
        .where(Tag.campaign_id == campaign_id)
        .where(Tag.reference_type == resource_type.value)
        .where(Tag.reference_id == resource_id)
        .order_by(Tag.id)
    ).all()
    for tag in linked_tags:
        promote_tag_reference(db, tag, resource_type, resource_id)

    labels_to_resolve = {
        normalize_tag_label(label): label
        for label in [
            *candidate_labels(resource_type, resource),
            *previous_labels,
        ]
        if normalize_tag_label(label)
    }
    for label in labels_to_resolve.values():
        resolve_pending_tags_for_resource(
            db,
            campaign_id,
            resource_type,
            label,
        )
