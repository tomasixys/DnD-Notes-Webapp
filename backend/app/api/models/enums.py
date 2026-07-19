from enum import Enum


class ResourceType(str, Enum):
    SESSION = "session"
    PERSON = "person"
    LOCATION = "location"
    FACTION = "faction"


class TagResolutionState(str, Enum):
    PASSIVE = "passive"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class CoinType(str, Enum):
    CP = "cp"
    SP = "sp"
    EP = "ep"
    GP = "gp"
    PP = "pp"

