"""Write tag assignments and relationship assignments for resources."""

from collections.abc import Callable, Iterable

from sqlmodel import Session, select

from app.models.api import ParsedTag
from app.models.database import Tag, TagAssignment
from app.models.enums import RelationshipType, ResourceType, TagResolutionState

from .references import get_or_create_tag_definition
from .syntax import clean_tag_label, normalize_tag_label, parse_tag


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


def _replace_assignments(
    db: Session,
    campaign_id: int,
    owner_type: ResourceType,
    owner_id: int,
    relationship_type: RelationshipType,
    parsed_tags: Iterable[ParsedTag],
    validate_tag: Callable[[Tag], None] | None = None,
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

    for parsed in parsed_tags:
        tag = get_or_create_tag_definition(db, campaign_id, parsed)
        if validate_tag is not None:
            validate_tag(tag)
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


def sync_resource_tags(
    db: Session,
    campaign_id: int,
    owner_type: ResourceType,
    owner_id: int,
    raw_tags: Iterable[str],
) -> None:
    parsed_tags: dict[str, ParsedTag] = {}
    for raw_tag in raw_tags:
        parsed = parse_tag(raw_tag)
        if parsed is not None:
            parsed_tags.setdefault(parsed.key, parsed)

    _replace_assignments(
        db,
        campaign_id,
        owner_type,
        owner_id,
        RelationshipType.ASSOCIATED_WITH,
        parsed_tags.values(),
    )


def _parse_relationship_reference(
    value: str,
    reference_type: ResourceType,
) -> ParsedTag | None:
    cleaned = clean_tag_label(value)
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
    parsed = _parse_relationship_reference(raw_reference, reference_type)

    def prevent_self_reference(tag: Tag) -> None:
        if owner_type == reference_type and tag.reference_id == owner_id:
            raise ValueError("A resource cannot reference itself")

    _replace_assignments(
        db,
        campaign_id,
        owner_type,
        owner_id,
        relationship_type,
        [parsed] if parsed is not None else [],
        validate_tag=prevent_self_reference,
    )


def handle_tags_of_deleted_resource(
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
