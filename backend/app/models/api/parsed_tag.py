from dataclasses import dataclass

from app.models.enums import ResourceType


@dataclass(frozen=True)
class ParsedTag:
    label: str
    normalized_label: str
    reference_type: ResourceType | None

    @property
    def key(self) -> str:
        prefix = self.reference_type.value if self.reference_type else "passive"
        return f"{prefix}:{self.normalized_label}"
