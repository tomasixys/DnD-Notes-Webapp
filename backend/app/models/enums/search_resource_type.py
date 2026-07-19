from enum import Enum


class SearchResourceType(str, Enum):
    SESSION = "session"
    PERSON = "person"
    LOCATION = "location"
    FACTION = "faction"
