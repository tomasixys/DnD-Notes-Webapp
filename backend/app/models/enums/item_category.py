from enum import Enum


class ItemCategory(str, Enum):
    EQUIPMENT = "equipment"
    VALUABLE = "valuable"
    CONSUMABLE = "consumable"
