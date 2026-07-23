from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import InventoryAccessRole

if TYPE_CHECKING:
    from .campaign import Campaign
    from .character import CharacterProfile
    from .inventory_item import InventoryItem
    from .purse import Purse


class Inventory(SQLModel, table=True):
    """A campaign-scoped collection of items and currency."""

    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        index=True,
    )
    name: str = "Party Inventory"
    description: str = ""

    campaign: "Campaign" = Relationship(back_populates="inventories")
    purse: "Purse" = Relationship(
        back_populates="inventory",
        cascade_delete=True,
        passive_deletes=True,
        sa_relationship_kwargs={"uselist": False},
    )
    items: list["InventoryItem"] = Relationship(
        back_populates="inventory",
        cascade_delete=True,
        passive_deletes=True,
    )
    access_grants: list["InventoryAccess"] = Relationship(
        back_populates="inventory",
        cascade_delete=True,
        passive_deletes=True,
    )


class InventoryAccess(SQLModel, table=True):
    """A character's ownership or management access to an inventory."""

    inventory_id: int = Field(
        foreign_key="inventory.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    character_person_id: int = Field(
        foreign_key="characterprofile.person_id",
        ondelete="CASCADE",
        primary_key=True,
        index=True,
    )
    role: InventoryAccessRole = Field(
        default=InventoryAccessRole.OWNER,
        sa_type=SAEnum(
            InventoryAccessRole,
            values_callable=lambda enum: [member.value for member in enum],
            native_enum=False,
            create_constraint=True,
            name="inventory_access_role",
        ),
    )

    inventory: Inventory = Relationship(back_populates="access_grants")
    character_profile: "CharacterProfile" = Relationship(
        back_populates="inventory_access"
    )
