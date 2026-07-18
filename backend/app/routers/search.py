import re
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy import String, cast, or_

from app.database import get_session
from app.models import Person, Faction, Location, ResourceType, SessionNote, SearchResultDto, SearchResponseDto, SearchQueryDto, SearchResourceType
from app.routers.campaigns import verify_campaign
from app.tag_handler import get_resource_tags, get_tag_matching_owner_ids

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/search",
    tags=["search"],
)


@dataclass(frozen=True)
class SearchField:
    name: str
    value: str
    weight: float

def parse_requested_types(
    types: list[str] | None,
) -> list[SearchResourceType]:
    if not types or not any(types):
        return list(SearchResourceType)

    try:
        return list(
            dict.fromkeys(
                SearchResourceType(value.strip())
                for value in types
            )
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Unknown search resource type",
        )

def create_like_pattern(query: str) -> str:
    escaped_query = (
        query
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    return f"%{escaped_query}%"



def get_people_matches(campaign_id: int, pattern: str, db: Session) -> list[Person]:
    tag_owner_ids = get_tag_matching_owner_ids(
        db, campaign_id, ResourceType.PERSON, pattern
    )
    conditions = [
        Person.name.ilike(pattern, escape="\\"),
        Person.role.ilike(pattern, escape="\\"),
        Person.faction.ilike(pattern, escape="\\"),
        Person.location.ilike(pattern, escape="\\"),
        Person.description.ilike(pattern, escape="\\"),
    ]
    if tag_owner_ids:
        conditions.append(Person.id.in_(tag_owner_ids))

    statement = (
        select(Person)
        .where(Person.campaign_id == campaign_id)
        .where(or_(*conditions))
    )
    return db.exec(statement).all()

def get_faction_matches(campaign_id: int, pattern: str, db: Session) -> list[Faction]:
    tag_owner_ids = get_tag_matching_owner_ids(
        db, campaign_id, ResourceType.FACTION, pattern
    )
    conditions = [
        Faction.name.ilike(pattern, escape="\\"),
        Faction.type.ilike(pattern, escape="\\"),
        Faction.location.ilike(pattern, escape="\\"),
        Faction.description.ilike(pattern, escape="\\"),
    ]
    if tag_owner_ids:
        conditions.append(Faction.id.in_(tag_owner_ids))

    statement = (
        select(Faction)
        .where(Faction.campaign_id == campaign_id)
        .where(or_(*conditions))
    )
    return db.exec(statement).all()

def get_location_matches(campaign_id: int, pattern: str, db: Session) -> list[Location]:
    tag_owner_ids = get_tag_matching_owner_ids(
        db, campaign_id, ResourceType.LOCATION, pattern
    )
    conditions = [
        Location.name.ilike(pattern, escape="\\"),
        Location.type.ilike(pattern, escape="\\"),
        Location.parent_location.ilike(pattern, escape="\\"),
        Location.description.ilike(pattern, escape="\\"),
    ]
    if tag_owner_ids:
        conditions.append(Location.id.in_(tag_owner_ids))

    statement = (
        select(Location)
        .where(Location.campaign_id == campaign_id)
        .where(or_(*conditions))
    )
    return db.exec(statement).all()

def get_session_matches(campaign_id: int, pattern: str, db: Session) -> list[SessionNote]:
    tag_owner_ids = get_tag_matching_owner_ids(
        db, campaign_id, ResourceType.SESSION, pattern
    )
    conditions = [
        SessionNote.title.ilike(pattern, escape="\\"),
        SessionNote.date.ilike(pattern, escape="\\"),
        cast(SessionNote.session_number, String).ilike(pattern, escape="\\"),
        SessionNote.description.ilike(pattern, escape="\\"),
    ]
    if tag_owner_ids:
        conditions.append(SessionNote.id.in_(tag_owner_ids))

    statement = (
        select(SessionNote)
        .where(SessionNote.campaign_id == campaign_id)
        .where(or_(*conditions))
    )
    return db.exec(statement).all()



def get_faction_search_fields(faction: Faction, db: Session) -> list[SearchField]:
    return [
        SearchField("name", faction.name, 1.0),
        SearchField("type", faction.type, 0.7),
        SearchField("location", faction.location, 0.7),
        SearchField("tags", " ".join(get_resource_tags(db, ResourceType.FACTION, faction.id)), 0.85),
        SearchField("description", faction.description, 0.55),
    ]

def get_location_search_fields(location: Location, db: Session) -> list[SearchField]:
    return [
        SearchField("name", location.name, 1.0),
        SearchField("type", location.type, 0.7),
        SearchField("tags", " ".join(get_resource_tags(db, ResourceType.LOCATION, location.id)), 0.85),
        SearchField("description", location.description, 0.55),
        SearchField("parent_location", location.parent_location, 0.7),
    ]

def get_session_search_fields(session: SessionNote, db: Session) -> list[SearchField]:
    return [
        SearchField("title", session.title, 1.0),
        SearchField("date", session.date, 0.65),
        SearchField("tags", " ".join(get_resource_tags(db, ResourceType.SESSION, session.id)), 0.85),
        SearchField("description", session.description, 0.55),
        SearchField("session_number", str(session.session_number), 0.65),
    ]

def get_person_search_fields(person: Person, db: Session) -> list[SearchField]:
    return [
        SearchField( name="name", value=person.name, weight=1.0, ),
        SearchField( name="role", value=person.role, weight=0.7, ),
        SearchField( name="faction", value=person.faction, weight=0.7, ),
        SearchField( name="location", value=person.location, weight=0.7, ),
        SearchField( name="tags", value=" ".join(get_resource_tags(db, ResourceType.PERSON, person.id)), weight=0.85, ),
        SearchField( name="description", value=person.description, weight=0.55, ),
    ]



def calculate_match_quality(
    value: str,
    query: str,
) -> float:
    text = value.casefold()
    phrase = query.casefold()

    if not text or phrase not in text:
        return 0.0
    elif text == phrase:
        return 1.0
    elif text.startswith(phrase):
        return 0.9
    elif re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text):
        return 0.8
    else:
        return 0.65

def evaluate_search_fields(
    query: str,
    fields: list[SearchField],
) -> tuple[list[str], float]:
    matches: list[tuple[str, float]] = []

    for field in fields:
        quality = calculate_match_quality(field.value, query)

        if quality == 0:
            continue

        matches.append((field.name, field.weight * quality))

    if not matches:
        return [], 0.0

    matched_fields = list( dict.fromkeys( field_name for field_name, _ in matches ) )
    additional_field_bonus = min( 0.15, 0.03 * (len(matched_fields) - 1) )

    best_score = max( score for _, score in matches )
    relevance = min(1.0, best_score + additional_field_bonus)

    return matched_fields, round(relevance, 3)




@router.post("")
def search_campaign(
    campaign_id: int,
    queryDto: SearchQueryDto,
    db: Session = Depends(get_session),
) -> SearchResponseDto:
    verify_campaign(campaign_id, db)

    query = queryDto.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Search query cannot be blank")

    requested_types = parse_requested_types(queryDto.resource_types)
    pattern = create_like_pattern(query)

    matching_people = get_people_matches(campaign_id, pattern, db) if SearchResourceType.PERSON in requested_types else []
    matching_factions = get_faction_matches(campaign_id, pattern, db) if SearchResourceType.FACTION in requested_types else []
    matching_locations = get_location_matches(campaign_id, pattern, db) if SearchResourceType.LOCATION in requested_types else []
    matching_sessions = get_session_matches(campaign_id, pattern, db) if SearchResourceType.SESSION in requested_types else []

    results: list[SearchResultDto] = []

    for person in matching_people:
        matched_fields, relevance = evaluate_search_fields(
            query,
            get_person_search_fields(person, db),
        )
        results.append(
            SearchResultDto(
                campaign_id=campaign_id,
                resource_type=SearchResourceType.PERSON,
                resource_id=person.id,
                title=person.name,
                context=person.role or "",
                snippet=person.description or "",
                matched_fields=matched_fields,
                relevance=relevance,
            )
        )
    for faction in matching_factions:
        matched_fields, relevance = evaluate_search_fields(
            query,
            get_faction_search_fields(faction, db),
        )
        results.append(
            SearchResultDto(
                campaign_id = campaign_id,
                resource_type = SearchResourceType.FACTION,
                resource_id = faction.id,
                title = faction.name,
                context = faction.type or "",
                snippet = faction.description or "",
                matched_fields = matched_fields,
                relevance = relevance,
            )
        )
    for location in matching_locations:
        matched_fields, relevance = evaluate_search_fields(
            query,
            get_location_search_fields(location, db),
        )
        results.append(
            SearchResultDto(
                campaign_id = campaign_id,
                resource_type = SearchResourceType.LOCATION,
                resource_id = location.id,
                title = location.name,
                context = location.type or "",
                snippet = location.description or "",
                matched_fields = matched_fields,
                relevance = relevance,
            )
        )
    for session in matching_sessions:
        matched_fields, relevance = evaluate_search_fields(
            query,
            get_session_search_fields(session, db),
        )
        results.append(
            SearchResultDto(
                campaign_id = campaign_id,
                resource_type = SearchResourceType.SESSION,
                resource_id = session.id,
                title = session.title,
                context = f"Session {session.session_number}",
                snippet = session.description or "",
                matched_fields = matched_fields,
                relevance = relevance,
            )
        )

    results.sort(key=lambda result: (-result.relevance, result.title.casefold()))

    return SearchResponseDto(
        query=query,
        searched_resource_types=requested_types,
        total_count=len(results),
        results=results,
    )
