from sqlmodel import SQLModel

from app.models.enums import RelationshipType, ResourceType, TagResolutionState


class ResourceTagRead(SQLModel):
    value: str
    label: str
    reference_type: ResourceType | None = None
    reference_id: int | None = None
    relationship_type: RelationshipType | None = None
    resolution_state: TagResolutionState
