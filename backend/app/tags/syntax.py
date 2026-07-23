"""Pure parsing, normalization, key-building, and display formatting."""

from typing import Protocol

from app.models.api import ParsedTag
from app.models.enums import ResourceType


class FormattableTag(Protocol):
    label: str
    reference_type: str | None


def clean_tag_label(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_tag_label(value: str) -> str:
    return clean_tag_label(value).casefold()


def resolved_tag_key(resource_type: ResourceType, reference_id: int) -> str:
    return f"reference:{resource_type.value}:{reference_id}"


def parse_tag(value: str) -> ParsedTag | None:
    cleaned = clean_tag_label(value)
    if not cleaned:
        return None

    prefix, separator, remainder = cleaned.partition(":")
    reference_type: ResourceType | None = None
    label = cleaned

    if separator and remainder.strip():
        try:
            reference_type = ResourceType(prefix.strip().casefold())
            label = clean_tag_label(remainder)
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


def format_tag(tag: FormattableTag) -> str:
    if tag.reference_type:
        return f"{tag.reference_type}:{tag.label}"
    return tag.label
