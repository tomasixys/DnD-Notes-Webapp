from enum import Enum


class RelationshipType(str, Enum):
    ASSOCIATED_WITH = "associated_with"
    MEMBER_OF = "member_of"
    LOCATED_IN = "located_in"
    PART_OF = "part_of"
    BASED_IN = "based_in"
