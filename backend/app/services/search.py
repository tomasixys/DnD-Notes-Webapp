import re

from fastapi import HTTPException
from sqlalchemy import String, cast, or_
from sqlmodel import select

from app.models.api import (
    SearchField,
    SearchQueryDto,
    SearchResponseDto,
    SearchResultDto,
)
from app.models.database import (
    BackstoryNote,
    CharacterNote,
    Faction,
    Location,
    Person,
    SessionNote,
)
from app.models.enums import RelationshipType, ResourceType
from app.services.campaign_context import CampaignContext
from app.tags import (
    get_resource_relationship,
    get_resource_tags,
    get_tag_matching_owner_ids,
)


SEARCHABLE_RESOURCE_TYPES = tuple(ResourceType)


def _create_like_pattern(query: str) -> str:
    escaped_query = (
        query.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped_query}%"


def _calculate_match_quality(value: str, query: str) -> float:
    text = value.casefold()
    phrase = query.casefold()

    if not text or phrase not in text:
        return 0.0
    if text == phrase:
        return 1.0
    if text.startswith(phrase):
        return 0.9
    if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text):
        return 0.8
    return 0.65


def _evaluate_search_fields(
    query: str,
    fields: list[SearchField],
) -> tuple[list[str], float]:
    matches: list[tuple[str, float]] = []
    for field in fields:
        quality = _calculate_match_quality(field.value, query)
        if quality:
            matches.append((field.name, field.weight * quality))

    if not matches:
        return [], 0.0

    matched_fields = list(
        dict.fromkeys(field_name for field_name, _ in matches)
    )
    additional_field_bonus = min(
        0.15,
        0.03 * (len(matched_fields) - 1),
    )
    relevance = min(
        1.0,
        max(score for _, score in matches) + additional_field_bonus,
    )
    return matched_fields, round(relevance, 3)


class SearchService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    def search(self, request: SearchQueryDto) -> SearchResponseDto:
        query = request.query.strip()
        if not query:
            raise HTTPException(
                status_code=422,
                detail="Search query cannot be blank",
            )

        requested_types = self._parse_requested_types(
            request.resource_types
        )
        pattern = _create_like_pattern(query)
        results: list[SearchResultDto] = []

        if ResourceType.PERSON in requested_types:
            results.extend(
                self._person_result(person, query)
                for person in self._find_people(pattern)
            )
        if ResourceType.FACTION in requested_types:
            results.extend(
                self._faction_result(faction, query)
                for faction in self._find_factions(pattern)
            )
        if ResourceType.LOCATION in requested_types:
            results.extend(
                self._location_result(location, query)
                for location in self._find_locations(pattern)
            )
        if ResourceType.SESSION in requested_types:
            results.extend(
                self._session_result(session, query)
                for session in self._find_sessions(pattern)
            )
        if ResourceType.CHARACTER_NOTE in requested_types:
            results.extend(
                self._note_result(
                    note,
                    query,
                    ResourceType.CHARACTER_NOTE,
                )
                for note in self._find_character_notes(pattern)
            )
        if ResourceType.BACKSTORY_NOTE in requested_types:
            results.extend(
                self._note_result(
                    note,
                    query,
                    ResourceType.BACKSTORY_NOTE,
                )
                for note in self._find_backstory_notes(pattern)
            )

        results.sort(
            key=lambda result: (
                -result.relevance,
                result.title.casefold(),
            )
        )
        return SearchResponseDto(
            query=query,
            searched_resource_types=requested_types,
            total_count=len(results),
            results=results,
        )

    @staticmethod
    def _parse_requested_types(
        requested_types: list[str] | None,
    ) -> list[ResourceType]:
        if not requested_types or not any(requested_types):
            return list(SEARCHABLE_RESOURCE_TYPES)

        try:
            return list(
                dict.fromkeys(
                    ResourceType(value.strip())
                    for value in requested_types
                )
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Unknown search resource type",
            )

    def _tag_owner_ids(
        self,
        resource_type: ResourceType,
        pattern: str,
    ) -> list[int]:
        return get_tag_matching_owner_ids(
            self.db,
            self.context.campaign_id,
            resource_type,
            pattern,
        )

    def _find_people(self, pattern: str) -> list[Person]:
        conditions = [
            Person.name.ilike(pattern, escape="\\"),
            Person.role.ilike(pattern, escape="\\"),
            Person.description.ilike(pattern, escape="\\"),
        ]
        tag_owner_ids = self._tag_owner_ids(
            ResourceType.PERSON,
            pattern,
        )
        if tag_owner_ids:
            conditions.append(Person.id.in_(tag_owner_ids))

        return self.db.exec(
            select(Person)
            .where(
                Person.campaign_id == self.context.campaign_id
            )
            .where(or_(*conditions))
        ).all()

    def _find_factions(self, pattern: str) -> list[Faction]:
        conditions = [
            Faction.name.ilike(pattern, escape="\\"),
            Faction.type.ilike(pattern, escape="\\"),
            Faction.description.ilike(pattern, escape="\\"),
        ]
        tag_owner_ids = self._tag_owner_ids(
            ResourceType.FACTION,
            pattern,
        )
        if tag_owner_ids:
            conditions.append(Faction.id.in_(tag_owner_ids))

        return self.db.exec(
            select(Faction)
            .where(
                Faction.campaign_id == self.context.campaign_id
            )
            .where(or_(*conditions))
        ).all()

    def _find_locations(self, pattern: str) -> list[Location]:
        conditions = [
            Location.name.ilike(pattern, escape="\\"),
            Location.type.ilike(pattern, escape="\\"),
            Location.description.ilike(pattern, escape="\\"),
        ]
        tag_owner_ids = self._tag_owner_ids(
            ResourceType.LOCATION,
            pattern,
        )
        if tag_owner_ids:
            conditions.append(Location.id.in_(tag_owner_ids))

        return self.db.exec(
            select(Location)
            .where(
                Location.campaign_id == self.context.campaign_id
            )
            .where(or_(*conditions))
        ).all()

    def _find_sessions(self, pattern: str) -> list[SessionNote]:
        conditions = [
            SessionNote.title.ilike(pattern, escape="\\"),
            SessionNote.date.ilike(pattern, escape="\\"),
            cast(SessionNote.session_number, String).ilike(
                pattern,
                escape="\\",
            ),
            SessionNote.content.ilike(pattern, escape="\\"),
        ]
        tag_owner_ids = self._tag_owner_ids(
            ResourceType.SESSION,
            pattern,
        )
        if tag_owner_ids:
            conditions.append(SessionNote.id.in_(tag_owner_ids))

        return self.db.exec(
            select(SessionNote)
            .where(
                SessionNote.campaign_id == self.context.campaign_id
            )
            .where(or_(*conditions))
        ).all()

    def _find_character_notes(
        self,
        pattern: str,
    ) -> list[CharacterNote]:
        conditions = [
            CharacterNote.title.ilike(pattern, escape="\\"),
            CharacterNote.content.ilike(pattern, escape="\\"),
            Person.name.ilike(pattern, escape="\\"),
        ]
        tag_owner_ids = self._tag_owner_ids(
            ResourceType.CHARACTER_NOTE,
            pattern,
        )
        if tag_owner_ids:
            conditions.append(CharacterNote.id.in_(tag_owner_ids))

        return self.db.exec(
            select(CharacterNote)
            .join(
                Person,
                Person.id == CharacterNote.character_person_id,
            )
            .where(
                CharacterNote.campaign_id
                == self.context.campaign_id
            )
            .where(or_(*conditions))
        ).all()

    def _find_backstory_notes(
        self,
        pattern: str,
    ) -> list[BackstoryNote]:
        conditions = [
            BackstoryNote.title.ilike(pattern, escape="\\"),
            BackstoryNote.content.ilike(pattern, escape="\\"),
            Person.name.ilike(pattern, escape="\\"),
        ]
        tag_owner_ids = self._tag_owner_ids(
            ResourceType.BACKSTORY_NOTE,
            pattern,
        )
        if tag_owner_ids:
            conditions.append(BackstoryNote.id.in_(tag_owner_ids))

        return self.db.exec(
            select(BackstoryNote)
            .join(
                Person,
                Person.id == BackstoryNote.character_person_id,
            )
            .where(
                BackstoryNote.campaign_id
                == self.context.campaign_id
            )
            .where(or_(*conditions))
        ).all()

    def _person_result(
        self,
        person: Person,
        query: str,
    ) -> SearchResultDto:
        faction = get_resource_relationship(
            self.db,
            ResourceType.PERSON,
            person.id,
            RelationshipType.MEMBER_OF,
        )
        location = get_resource_relationship(
            self.db,
            ResourceType.PERSON,
            person.id,
            RelationshipType.LOCATED_IN,
        )
        matched_fields, relevance = _evaluate_search_fields(
            query,
            [
                SearchField("name", person.name, 1.0),
                SearchField("role", person.role, 0.7),
                SearchField(
                    "faction",
                    faction.label if faction else "",
                    0.7,
                ),
                SearchField(
                    "location",
                    location.label if location else "",
                    0.7,
                ),
                self._tag_field(ResourceType.PERSON, person.id),
                SearchField(
                    "description",
                    person.description,
                    0.55,
                ),
            ],
        )
        return SearchResultDto(
            campaign_id=self.context.campaign_id,
            resource_type=ResourceType.PERSON,
            resource_id=person.id,
            title=person.name,
            context=person.role or "",
            snippet=person.description or "",
            matched_fields=matched_fields,
            relevance=relevance,
        )

    def _faction_result(
        self,
        faction: Faction,
        query: str,
    ) -> SearchResultDto:
        location = get_resource_relationship(
            self.db,
            ResourceType.FACTION,
            faction.id,
            RelationshipType.BASED_IN,
        )
        matched_fields, relevance = _evaluate_search_fields(
            query,
            [
                SearchField("name", faction.name, 1.0),
                SearchField("type", faction.type, 0.7),
                SearchField(
                    "location",
                    location.label if location else "",
                    0.7,
                ),
                self._tag_field(ResourceType.FACTION, faction.id),
                SearchField(
                    "description",
                    faction.description,
                    0.55,
                ),
            ],
        )
        return SearchResultDto(
            campaign_id=self.context.campaign_id,
            resource_type=ResourceType.FACTION,
            resource_id=faction.id,
            title=faction.name,
            context=faction.type or "",
            snippet=faction.description or "",
            matched_fields=matched_fields,
            relevance=relevance,
        )

    def _location_result(
        self,
        location: Location,
        query: str,
    ) -> SearchResultDto:
        parent_location = get_resource_relationship(
            self.db,
            ResourceType.LOCATION,
            location.id,
            RelationshipType.PART_OF,
        )
        matched_fields, relevance = _evaluate_search_fields(
            query,
            [
                SearchField("name", location.name, 1.0),
                SearchField("type", location.type, 0.7),
                self._tag_field(ResourceType.LOCATION, location.id),
                SearchField(
                    "description",
                    location.description,
                    0.55,
                ),
                SearchField(
                    "parent_location",
                    parent_location.label if parent_location else "",
                    0.7,
                ),
            ],
        )
        return SearchResultDto(
            campaign_id=self.context.campaign_id,
            resource_type=ResourceType.LOCATION,
            resource_id=location.id,
            title=location.name,
            context=location.type or "",
            snippet=location.description or "",
            matched_fields=matched_fields,
            relevance=relevance,
        )

    def _session_result(
        self,
        session: SessionNote,
        query: str,
    ) -> SearchResultDto:
        matched_fields, relevance = _evaluate_search_fields(
            query,
            [
                SearchField("title", session.title, 1.0),
                SearchField("date", session.date, 0.65),
                self._tag_field(ResourceType.SESSION, session.id),
                SearchField(
                    "description",
                    session.content,
                    0.55,
                ),
                SearchField(
                    "session_number",
                    str(session.session_number),
                    0.65,
                ),
            ],
        )
        return SearchResultDto(
            campaign_id=self.context.campaign_id,
            resource_type=ResourceType.SESSION,
            resource_id=session.id,
            title=session.title,
            context=f"Session {session.session_number}",
            snippet=session.content or "",
            matched_fields=matched_fields,
            relevance=relevance,
        )

    def _note_result(
        self,
        note: CharacterNote | BackstoryNote,
        query: str,
        resource_type: ResourceType,
    ) -> SearchResultDto:
        character = self.db.get(
            Person,
            note.character_person_id,
        )
        character_name = (
            character.name if character else "Unknown character"
        )
        matched_fields, relevance = _evaluate_search_fields(
            query,
            [
                SearchField("title", note.title, 1.0),
                self._tag_field(resource_type, note.id),
                SearchField("character", character_name, 0.7),
                SearchField("content", note.content, 0.55),
            ],
        )
        context_label = (
            "Character note"
            if resource_type == ResourceType.CHARACTER_NOTE
            else "Backstory"
        )
        return SearchResultDto(
            campaign_id=self.context.campaign_id,
            resource_type=resource_type,
            resource_id=note.id,
            parent_resource_id=note.character_person_id,
            title=note.title,
            context=f"{context_label} Â· {character_name}",
            snippet=note.content or "",
            matched_fields=matched_fields,
            relevance=relevance,
        )

    def _tag_field(
        self,
        resource_type: ResourceType,
        resource_id: int,
    ) -> SearchField:
        return SearchField(
            "tags",
            " ".join(
                get_resource_tags(
                    self.db,
                    resource_type,
                    resource_id,
                )
            ),
            0.85,
        )
