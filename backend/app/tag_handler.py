from typing import Iterable

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models.database import (
    Faction,
    Location,
    Person,
    SessionNote,
    Tag,
    TagAssignment,
)
from app.models.api import ResourceTagRead, ParsedTag
from app.models.enums import RelationshipType, ResourceType, TagResolutionState



REFERENCE_MODELS = {
    ResourceType.PERSON: Person,
    ResourceType.LOCATION: Location,
    ResourceType.FACTION: Faction,
    ResourceType.SESSION: SessionNote,
}

def normalize_tag_label(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def resolved_tag_key(resource_type: ResourceType, reference_id: int) -> str:
    return f"reference:{resource_type.value}:{reference_id}"


def parse_tag(value: str) -> ParsedTag | None:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None

    prefix, separator, remainder = cleaned.partition(":")
    reference_type: ResourceType | None = None
    label = cleaned

    if separator and remainder.strip():
        try:
            reference_type = ResourceType(prefix.strip().casefold())
            label = " ".join(remainder.strip().split())
        except ValueError:
            # Unknown prefixes remain ordinary passive tags. This preserves
            # tags such as "status:neutral" without reserving every colon.
            pass

    normalized_label = normalize_tag_label(label)
    if not normalized_label:
        return None

    return ParsedTag(
        label=label,
        normalized_label=normalized_label,
        reference_type=reference_type,
    )


def format_tag(tag: Tag) -> str:
    if tag.reference_type:
        return f"{tag.reference_type}:{tag.label}"
    return tag.label


def _candidate_labels(resource_type: ResourceType, resource) -> list[str]:
    if resource_type == ResourceType.SESSION:
        return [
            resource.title,
            str(resource.session_number),
            f"session {resource.session_number}",
        ]
    return [resource.name]


def _canonical_label(resource_type: ResourceType, resource) -> str:
    if resource_type == ResourceType.SESSION:
        return resource.title
    return resource.name


def resolve_reference(
    db: Session,
    campaign_id: int,
    resource_type: ResourceType,
    label: str,
) -> tuple[int | None, TagResolutionState]:
    model = REFERENCE_MODELS[resource_type]
    resources = db.exec(
        select(model).where(model.campaign_id == campaign_id)
    ).all()
    normalized_label = normalize_tag_label(label)

    matches = [
        resource
        for resource in resources
        if any(
            normalize_tag_label(candidate) == normalized_label
            for candidate in _candidate_labels(resource_type, resource)
        )
    ]

    if len(matches) == 1:
        return matches[0].id, TagResolutionState.RESOLVED
    if len(matches) > 1:
        return None, TagResolutionState.AMBIGUOUS
    return None, TagResolutionState.UNRESOLVED


def _get_or_create_tag(
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
            resource = db.get(REFERENCE_MODELS[parsed.reference_type], reference_id)
            if resource is not None:
                label = _canonical_label(parsed.reference_type, resource)

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


def _merge_tags(db: Session, source: Tag, destination: Tag) -> Tag:
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


def _promote_resolved_tag(
    db: Session,
    tag: Tag,
    resource_type: ResourceType,
    reference_id: int,
) -> Tag:
    resource = db.get(REFERENCE_MODELS[resource_type], reference_id)
    if resource is None:
        return tag

    key = resolved_tag_key(resource_type, reference_id)
    canonical_label = _canonical_label(resource_type, resource)
    identity_tag = db.exec(
        select(Tag)
        .where(Tag.campaign_id == tag.campaign_id)
        .where(Tag.key == key)
    ).first()

    if identity_tag is not None and identity_tag.id != tag.id:
        tag = _merge_tags(db, tag, identity_tag)

    tag.key = key
    tag.label = canonical_label
    tag.normalized_label = normalize_tag_label(canonical_label)
    tag.reference_id = reference_id
    tag.resolution_state = TagResolutionState.RESOLVED.value
    db.add(tag)
    db.flush()
    return tag


def _cleanup_orphan_tags(db: Session, tag_ids: Iterable[int]) -> None:
    for tag_id in set(tag_ids):
        assignment = db.exec(
            select(TagAssignment.id)
            .where(TagAssignment.tag_id == tag_id)
            .limit(1)
        ).first()
        if assignment is None:
            tag = db.get(Tag, tag_id)
            if tag is not None:
                db.delete(tag)


def sync_resource_tags(
    db: Session,
    campaign_id: int,
    owner_type: ResourceType,
    owner_id: int,
    raw_tags: Iterable[str],
) -> None:
    existing_assignments = db.exec(
        select(TagAssignment)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(TagAssignment.owner_id == owner_id)
        .where(
            TagAssignment.relationship_type
            == RelationshipType.ASSOCIATED_WITH.value
        )
    ).all()
    old_tag_ids = [assignment.tag_id for assignment in existing_assignments]

    for assignment in existing_assignments:
        db.delete(assignment)
    db.flush()

    parsed_tags: dict[str, ParsedTag] = {}
    for raw_tag in raw_tags:
        parsed = parse_tag(raw_tag)
        if parsed is not None:
            parsed_tags.setdefault(parsed.key, parsed)

    for parsed in parsed_tags.values():
        tag = _get_or_create_tag(db, campaign_id, parsed)
        db.add(
            TagAssignment(
                tag_id=tag.id,
                owner_type=owner_type.value,
                owner_id=owner_id,
                relationship_type=RelationshipType.ASSOCIATED_WITH.value,
            )
        )

    db.flush()
    _cleanup_orphan_tags(db, old_tag_ids)


def _parse_relationship_reference(
    value: str,
    reference_type: ResourceType,
) -> ParsedTag | None:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None

    parsed = parse_tag(cleaned)
    label = (
        parsed.label
        if parsed is not None and parsed.reference_type == reference_type
        else cleaned
    )
    normalized_label = normalize_tag_label(label)
    if not normalized_label:
        return None

    return ParsedTag(
        label=label,
        normalized_label=normalized_label,
        reference_type=reference_type,
    )


def sync_resource_relationship(
    db: Session,
    campaign_id: int,
    owner_type: ResourceType,
    owner_id: int,
    relationship_type: RelationshipType,
    reference_type: ResourceType,
    raw_reference: str,
) -> None:
    existing_assignments = db.exec(
        select(TagAssignment)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(TagAssignment.owner_id == owner_id)
        .where(TagAssignment.relationship_type == relationship_type.value)
    ).all()
    old_tag_ids = [assignment.tag_id for assignment in existing_assignments]

    for assignment in existing_assignments:
        db.delete(assignment)
    db.flush()

    parsed = _parse_relationship_reference(raw_reference, reference_type)
    if parsed is not None:
        tag = _get_or_create_tag(db, campaign_id, parsed)
        if owner_type == reference_type and tag.reference_id == owner_id:
            raise ValueError("A resource cannot reference itself")
        db.add(
            TagAssignment(
                tag_id=tag.id,
                owner_type=owner_type.value,
                owner_id=owner_id,
                relationship_type=relationship_type.value,
            )
        )

    db.flush()
    _cleanup_orphan_tags(db, old_tag_ids)


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


def get_resource_tag_reads(
    db: Session,
    owner_type: ResourceType,
    owner_id: int,
) -> list[ResourceTagRead]:
    statement = (
        select(Tag, TagAssignment.relationship_type)
        .join(TagAssignment, TagAssignment.tag_id == Tag.id)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(TagAssignment.owner_id == owner_id)
        .where(
            TagAssignment.relationship_type
            == RelationshipType.ASSOCIATED_WITH.value
        )
        .order_by(Tag.reference_type, Tag.normalized_label, Tag.id)
    )

    return [
        ResourceTagRead(
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
        for tag, relationship_type in db.exec(statement).all()
    ]


def get_resource_relationship(
    db: Session,
    owner_type: ResourceType,
    owner_id: int,
    relationship_type: RelationshipType,
) -> ResourceTagRead | None:
    row = db.exec(
        select(Tag, TagAssignment.relationship_type)
        .join(TagAssignment, TagAssignment.tag_id == Tag.id)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(TagAssignment.owner_id == owner_id)
        .where(TagAssignment.relationship_type == relationship_type.value)
        .order_by(Tag.id)
    ).first()
    if row is None:
        return None

    tag, stored_relationship_type = row
    return ResourceTagRead(
        value=format_tag(tag),
        label=tag.label,
        reference_type=(
            ResourceType(tag.reference_type)
            if tag.reference_type
            else None
        ),
        reference_id=tag.reference_id,
        relationship_type=RelationshipType(stored_relationship_type),
        resolution_state=TagResolutionState(tag.resolution_state),
    )


def get_relationship_owner_reads(
    db: Session,
    campaign_id: int,
    target_type: ResourceType,
    target_id: int,
    owner_type: ResourceType,
    relationship_type: RelationshipType,
) -> list[ResourceTagRead]:
    model = REFERENCE_MODELS[owner_type]
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
            value=f"{owner_type.value}:{_canonical_label(owner_type, owner)}",
            label=_canonical_label(owner_type, owner),
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
            _promote_resolved_tag(
                db,
                tag,
                resource_type,
                reference_id,
            )
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
    resource = db.get(REFERENCE_MODELS[resource_type], resource_id)
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
        _promote_resolved_tag(
            db,
            tag,
            resource_type,
            resource_id,
        )

    labels_to_resolve = {
        normalize_tag_label(label): label
        for label in [*_candidate_labels(resource_type, resource), *previous_labels]
        if normalize_tag_label(label)
    }
    for label in labels_to_resolve.values():
        resolve_pending_tags_for_resource(
            db,
            campaign_id,
            resource_type,
            label,
        )


def handle_resource_deleted(
    db: Session,
    owner_type: ResourceType,
    owner_id: int,
) -> None:
    assignments = db.exec(
        select(TagAssignment)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(TagAssignment.owner_id == owner_id)
    ).all()
    old_tag_ids = [assignment.tag_id for assignment in assignments]
    for assignment in assignments:
        db.delete(assignment)

    referenced_tags = db.exec(
        select(Tag)
        .where(Tag.reference_type == owner_type.value)
        .where(Tag.reference_id == owner_id)
    ).all()
    for tag in referenced_tags:
        tag.reference_id = None
        tag.resolution_state = TagResolutionState.UNRESOLVED.value
        db.add(tag)

    db.flush()
    _cleanup_orphan_tags(db, old_tag_ids)
