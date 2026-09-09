from enum import Enum


class ResourceType(str, Enum):
    # The persisted/API value remains "session" for compatibility.
    EPISODE = "session"
    PERSON = "person"
    LOCATION = "location"
    FACTION = "faction"
    CHARACTER_NOTE = "character_note"
    BACKSTORY_NOTE = "backstory_note"
