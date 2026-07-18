from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    Faction,
    Location,
    Person,
    ResourceTagRead,
    ResourceType,
    SessionNote,
    Tag,
    TagAssignment,
    TagResolutionState,
)


REFERENCE_MODELS = {
    ResourceType.PERSON: Person,
    ResourceType.LOCATION: Location,
    ResourceType.FACTION: Faction,
    ResourceType.SESSION: SessionNote,
}


@dataclass(frozen=True)
class ParsedTag:
    label: str
    normalized_label: str
    reference_type: ResourceType | None

    @property
    def key(self) -> str:
        prefix = self.reference_type.value if self.reference_type else "passive"
        return f"{prefix}:{self.normalized_label}"


def normalize_tag_label(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


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
    tag = db.exec(
        select(Tag)
        .where(Tag.campaign_id == campaign_id)
        .where(Tag.key == parsed.key)
    ).first()

    if tag is None:
        tag = Tag(
            campaign_id=campaign_id,
            label=parsed.label,
            normalized_label=parsed.normalized_label,
            key=parsed.key,
            reference_type=(
                parsed.reference_type.value
                if parsed.reference_type
                else None
            ),
            resolution_state=TagResolutionState.PASSIVE.value,
        )

    if parsed.reference_type:
        reference_id, state = resolve_reference(
            db,
            campaign_id,
            parsed.reference_type,
            parsed.label,
        )
        tag.reference_id = reference_id
        tag.resolution_state = state.value
    else:
        tag.reference_id = None
        tag.resolution_state = TagResolutionState.PASSIVE.value

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
        .order_by(Tag.reference_type, Tag.normalized_label, Tag.id)
    )
    return [format_tag(tag) for tag in db.exec(statement).all()]


def get_resource_tag_reads(
    db: Session,
    owner_type: ResourceType,
    owner_id: int,
) -> list[ResourceTagRead]:
    statement = (
        select(Tag)
        .join(TagAssignment, TagAssignment.tag_id == Tag.id)
        .where(TagAssignment.owner_type == owner_type.value)
        .where(TagAssignment.owner_id == owner_id)
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
            resolution_state=TagResolutionState(tag.resolution_state),
        )
        for tag in db.exec(statement).all()
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
        tag.reference_id = reference_id
        tag.resolution_state = state.value
        db.add(tag)


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
