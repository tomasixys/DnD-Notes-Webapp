from enum import Enum


class InventoryAccessRole(str, Enum):
    OWNER = "owner"
    MANAGER = "manager"
