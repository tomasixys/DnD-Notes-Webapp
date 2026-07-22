from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import ItemCategory, ItemRarity

if TYPE_CHECKING:
    from .inventory import Inventory


class InventoryItem(SQLModel, table=True):
    """A stack of equivalent items contained in an inventory."""

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_inventoryitem_quantity_positive",
        ),
        CheckConstraint(
            "unit_value_cp IS NULL OR unit_value_cp >= 0",
            name="ck_inventoryitem_unit_value_non_negative",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    inventory_id: int = Field(
        foreign_key="inventory.id",
        ondelete="CASCADE",
        index=True,
    )
    name: str
    description: str = ""
    category: ItemCategory = Field(
        default=ItemCategory.EQUIPMENT,
        sa_type=SAEnum(
            ItemCategory,
            values_callable=lambda enum: [member.value for member in enum],
            native_enum=False,
            create_constraint=True,
            name="item_category",
        ),
    )
    rarity: ItemRarity | None = Field(
        default=None,
        sa_type=SAEnum(
            ItemRarity,
            values_callable=lambda enum: [member.value for member in enum],
            native_enum=False,
            create_constraint=True,
            name="item_rarity",
        ),
    )
    quantity: int = 1
    unit_value_cp: int | None = None

    inventory: "Inventory" = Relationship(back_populates="items")
