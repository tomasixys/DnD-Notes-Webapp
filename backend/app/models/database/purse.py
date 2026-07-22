from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import CurrencyDenomination

if TYPE_CHECKING:
    from .inventory import Inventory


class Purse(SQLModel, table=True):
    """The one purse belonging to an inventory."""

    inventory_id: int = Field(
        foreign_key="inventory.id",
        ondelete="CASCADE",
        primary_key=True,
    )

    inventory: "Inventory" = Relationship(back_populates="purse")
    balances: list["CurrencyBalance"] = Relationship(
        back_populates="purse",
        cascade_delete=True,
        passive_deletes=True,
    )


class CurrencyBalance(SQLModel, table=True):
    """The non-negative amount of one denomination held by a purse."""

    __table_args__ = (
        CheckConstraint(
            "amount >= 0",
            name="ck_currencybalance_amount_non_negative",
        ),
    )

    purse_id: int = Field(
        foreign_key="purse.inventory_id",
        ondelete="CASCADE",
        primary_key=True,
    )
    denomination: CurrencyDenomination = Field(
        primary_key=True,
        sa_type=SAEnum(
            CurrencyDenomination,
            values_callable=lambda enum: [member.value for member in enum],
            native_enum=False,
            create_constraint=True,
            name="currency_denomination",
        ),
    )
    amount: int = 0

    purse: Purse = Relationship(back_populates="balances")
