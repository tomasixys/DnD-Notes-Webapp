from enum import Enum
from sqlmodel import Field, SQLModel


class SearchResourceType(str, Enum):
    SESSION = "session"
    PERSON = "person"
    LOCATION = "location"
    FACTION = "faction"


class SearchQueryDto(SQLModel):
    query: str
    resource_types: list[str] = Field(default_factory=list)


class SearchResultDto(SQLModel):
    campaign_id: int
    resource_type: str
    resource_id: int
    title: str
    context: str
    snippet: str
    matched_fields: list[str] = Field(default_factory=list)
    relevance: float


class SearchResponseDto(SQLModel):
    query: str
    searched_resource_types: list[str] = Field(default_factory=list)
    total_count: int
    results: list[SearchResultDto] = Field(default_factory=list)
