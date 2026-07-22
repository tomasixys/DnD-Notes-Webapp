from enum import Enum


class ResourceType(str, Enum):
    SESSION = "session"
    PERSON = "person"
    LOCATION = "location"
    FACTION = "faction"
    CHARACTER_NOTE = "character_note"
    BACKSTORY_NOTE = "backstory_note"
