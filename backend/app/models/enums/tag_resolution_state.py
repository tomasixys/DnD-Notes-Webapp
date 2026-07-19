from enum import Enum


class TagResolutionState(str, Enum):
    PASSIVE = "passive"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
