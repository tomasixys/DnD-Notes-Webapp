import re
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy import String, cast, or_

from app.database import get_session
from app.models.database import (
    BackstoryNote,
    CharacterNote,
    Faction,
    Location,
    Person,
    SessionNote,
)
from app.models.api import (
    SearchField,
    SearchResultDto,
    SearchResponseDto,
    SearchQueryDto,
)
from app.models.enums import RelationshipType, ResourceType
from app.routers.campaigns import verify_campaign
from app.tags import (
    get_resource_relationship,
    get_resource_tags,
    get_tag_matching_owner_ids,
)

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/search",
    tags=["search"],
)

# All current resource types are searchable. This remains a separate collection
# so a future non-searchable ResourceType can be excluded without another enum.
SEARCHABLE_RESOURCE_TYPES = tuple(ResourceType)


def parse_requested_types(
    types: list[str] | None,
) -> list[ResourceType]:
    if not types or not any(types):
        return list(SEARCHABLE_RESOURCE_TYPES)

    try:
        return list(
            dict.fromkeys(
                ResourceType(value.strip())
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
        SessionNote.content.ilike(pattern, escape="\\"),
    ]
    if tag_owner_ids:
        conditions.append(SessionNote.id.in_(tag_owner_ids))

    statement = (
        select(SessionNote)
        .where(SessionNote.campaign_id == campaign_id)
        .where(or_(*conditions))
    )
    return db.exec(statement).all()


def get_character_note_matches(
    campaign_id: int,
    pattern: str,
    db: Session,
) -> list[CharacterNote]:
    tag_owner_ids = get_tag_matching_owner_ids(
        db, campaign_id, ResourceType.CHARACTER_NOTE, pattern
    )
    conditions = [
        CharacterNote.title.ilike(pattern, escape="\\"),
        CharacterNote.content.ilike(pattern, escape="\\"),
        Person.name.ilike(pattern, escape="\\"),
    ]
    if tag_owner_ids:
        conditions.append(CharacterNote.id.in_(tag_owner_ids))

    statement = (
        select(CharacterNote)
        .join(Person, Person.id == CharacterNote.character_person_id)
        .where(CharacterNote.campaign_id == campaign_id)
        .where(or_(*conditions))
    )
    return db.exec(statement).all()


def get_backstory_note_matches(
    campaign_id: int,
    pattern: str,
    db: Session,
) -> list[BackstoryNote]:
    tag_owner_ids = get_tag_matching_owner_ids(
        db, campaign_id, ResourceType.BACKSTORY_NOTE, pattern
    )
    conditions = [
        BackstoryNote.title.ilike(pattern, escape="\\"),
        BackstoryNote.content.ilike(pattern, escape="\\"),
        Person.name.ilike(pattern, escape="\\"),
    ]
    if tag_owner_ids:
        conditions.append(BackstoryNote.id.in_(tag_owner_ids))

    statement = (
        select(BackstoryNote)
        .join(Person, Person.id == BackstoryNote.character_person_id)
        .where(BackstoryNote.campaign_id == campaign_id)
        .where(or_(*conditions))
    )
    return db.exec(statement).all()



def get_faction_search_fields(faction: Faction, db: Session) -> list[SearchField]:
    location = get_resource_relationship(
        db,
        ResourceType.FACTION,
        faction.id,
        RelationshipType.BASED_IN,
    )
    return [
        SearchField("name", faction.name, 1.0),
        SearchField("type", faction.type, 0.7),
        SearchField("location", location.label if location else "", 0.7),
        SearchField("tags", " ".join(get_resource_tags(db, ResourceType.FACTION, faction.id)), 0.85),
        SearchField("description", faction.description, 0.55),
    ]

def get_location_search_fields(location: Location, db: Session) -> list[SearchField]:
    parent_location = get_resource_relationship(
        db,
        ResourceType.LOCATION,
        location.id,
        RelationshipType.PART_OF,
    )
    return [
        SearchField("name", location.name, 1.0),
        SearchField("type", location.type, 0.7),
        SearchField("tags", " ".join(get_resource_tags(db, ResourceType.LOCATION, location.id)), 0.85),
        SearchField("description", location.description, 0.55),
        SearchField(
            "parent_location",
            parent_location.label if parent_location else "",
            0.7,
        ),
    ]

def get_session_search_fields(session: SessionNote, db: Session) -> list[SearchField]:
    return [
        SearchField("title", session.title, 1.0),
        SearchField("date", session.date, 0.65),
        SearchField("tags", " ".join(get_resource_tags(db, ResourceType.SESSION, session.id)), 0.85),
        SearchField("description", session.content, 0.55),
        SearchField("session_number", str(session.session_number), 0.65),
    ]

def get_person_search_fields(person: Person, db: Session) -> list[SearchField]:
    faction = get_resource_relationship(
        db,
        ResourceType.PERSON,
        person.id,
        RelationshipType.MEMBER_OF,
    )
    location = get_resource_relationship(
        db,
        ResourceType.PERSON,
        person.id,
        RelationshipType.LOCATED_IN,
    )
    return [
        SearchField( name="name", value=person.name, weight=1.0, ),
        SearchField( name="role", value=person.role, weight=0.7, ),
        SearchField( name="faction", value=faction.label if faction else "", weight=0.7, ),
        SearchField( name="location", value=location.label if location else "", weight=0.7, ),
        SearchField( name="tags", value=" ".join(get_resource_tags(db, ResourceType.PERSON, person.id)), weight=0.85, ),
        SearchField( name="description", value=person.description, weight=0.55, ),
    ]


def get_character_note_search_fields(
    note: CharacterNote | BackstoryNote,
    resource_type: ResourceType,
    character_name: str,
    db: Session,
) -> list[SearchField]:
    return [
        SearchField("title", note.title, 1.0),
        SearchField("tags", " ".join(get_resource_tags(db, resource_type, note.id)), 0.85),
        SearchField("character", character_name, 0.7),
        SearchField("content", note.content, 0.55),
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

    matching_people = get_people_matches(campaign_id, pattern, db) if ResourceType.PERSON in requested_types else []
    matching_factions = get_faction_matches(campaign_id, pattern, db) if ResourceType.FACTION in requested_types else []
    matching_locations = get_location_matches(campaign_id, pattern, db) if ResourceType.LOCATION in requested_types else []
    matching_sessions = get_session_matches(campaign_id, pattern, db) if ResourceType.SESSION in requested_types else []
    matching_character_notes = (
        get_character_note_matches(campaign_id, pattern, db)
        if ResourceType.CHARACTER_NOTE in requested_types
        else []
    )
    matching_backstory_notes = (
        get_backstory_note_matches(campaign_id, pattern, db)
        if ResourceType.BACKSTORY_NOTE in requested_types
        else []
    )

    results: list[SearchResultDto] = []

    for person in matching_people:
        matched_fields, relevance = evaluate_search_fields(
            query,
            get_person_search_fields(person, db),
        )
        results.append(
            SearchResultDto(
                campaign_id=campaign_id,
                resource_type=ResourceType.PERSON,
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
                resource_type = ResourceType.FACTION,
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
                resource_type = ResourceType.LOCATION,
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
                resource_type = ResourceType.SESSION,
                resource_id = session.id,
                title = session.title,
                context = f"Session {session.session_number}",
                snippet = session.content or "",
                matched_fields = matched_fields,
                relevance = relevance,
            )
        )

    for note in matching_character_notes:
        character = db.get(Person, note.character_person_id)
        character_name = character.name if character else "Unknown character"
        matched_fields, relevance = evaluate_search_fields(
            query,
            get_character_note_search_fields(
                note,
                ResourceType.CHARACTER_NOTE,
                character_name,
                db,
            ),
        )
        results.append(
            SearchResultDto(
                campaign_id=campaign_id,
                resource_type=ResourceType.CHARACTER_NOTE,
                resource_id=note.id,
                parent_resource_id=note.character_person_id,
                title=note.title,
                context=f"Character note · {character_name}",
                snippet=note.content or "",
                matched_fields=matched_fields,
                relevance=relevance,
            )
        )

    for note in matching_backstory_notes:
        character = db.get(Person, note.character_person_id)
        character_name = character.name if character else "Unknown character"
        matched_fields, relevance = evaluate_search_fields(
            query,
            get_character_note_search_fields(
                note,
                ResourceType.BACKSTORY_NOTE,
                character_name,
                db,
            ),
        )
        results.append(
            SearchResultDto(
                campaign_id=campaign_id,
                resource_type=ResourceType.BACKSTORY_NOTE,
                resource_id=note.id,
                parent_resource_id=note.character_person_id,
                title=note.title,
                context=f"Backstory · {character_name}",
                snippet=note.content or "",
                matched_fields=matched_fields,
                relevance=relevance,
            )
        )

    results.sort(key=lambda result: (-result.relevance, result.title.casefold()))

    return SearchResponseDto(
        query=query,
        searched_resource_types=requested_types,
        total_count=len(results),
        results=results,
    )
