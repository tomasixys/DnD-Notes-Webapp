from sqlmodel import SQLModel

from .enums import ResourceType, TagResolutionState


class ResourceTagRead(SQLModel):
    value: str
    label: str
    reference_type: ResourceType | None = None
    reference_id: int | None = None
    resolution_state: TagResolutionState
