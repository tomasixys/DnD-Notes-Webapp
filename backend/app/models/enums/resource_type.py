from enum import Enum


class ResourceType(str, Enum):
    SESSION = "session"
    PERSON = "person"
    LOCATION = "location"
    FACTION = "faction"
