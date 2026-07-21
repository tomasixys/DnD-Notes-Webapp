from dataclasses import dataclass

from sqlmodel import Field, SQLModel

from app.models.enums import ResourceType


@dataclass(frozen=True)
class SearchField:
    name: str
    value: str
    weight: float


class SearchQueryDto(SQLModel):
    query: str
    resource_types: list[str] = Field(default_factory=list)


class SearchResultDto(SQLModel):
    campaign_id: int
    resource_type: ResourceType
    resource_id: int
    parent_resource_id: int | None = None
    title: str
    context: str
    snippet: str
    matched_fields: list[str] = Field(default_factory=list)
    relevance: float


class SearchResponseDto(SQLModel):
    query: str
    searched_resource_types: list[ResourceType] = Field(default_factory=list)
    total_count: int
    results: list[SearchResultDto] = Field(default_factory=list)
