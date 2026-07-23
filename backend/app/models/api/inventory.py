from decimal import Decimal

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.models.enums import (
    CurrencyDenomination,
    InventoryAccessRole,
    ItemCategory,
    ItemRarity,
)


class MoneyAmount(SQLModel):
    """A user-facing monetary amount in a selected denomination."""

    amount: Decimal = Field(
        ge=0,
        max_digits=16,
        decimal_places=4,
    )
    denomination: CurrencyDenomination = CurrencyDenomination.GOLD


class PurseBalances(SQLModel):
    cp: int = Field(default=0, ge=0)
    sp: int = Field(default=0, ge=0)
    ep: int = Field(default=0, ge=0)
    gp: int = Field(default=0, ge=0)
    pp: int = Field(default=0, ge=0)


class PurseBalancesUpdate(SQLModel):
    """A partial balance update; omitted denominations remain unchanged."""

    cp: int | None = Field(default=None, ge=0)
    sp: int | None = Field(default=None, ge=0)
    ep: int | None = Field(default=None, ge=0)
    gp: int | None = Field(default=None, ge=0)
    pp: int | None = Field(default=None, ge=0)

    @field_validator("cp", "sp", "ep", "gp", "pp")
    @classmethod
    def reject_explicit_null(cls, value: int | None) -> int:
        if value is None:
            raise ValueError("A provided balance must be an integer")
        return value


class PurseUpdate(SQLModel):
    balances: PurseBalancesUpdate


class PurseRead(SQLModel):
    balances: PurseBalances
    total_value: MoneyAmount


class InventoryMemberRead(SQLModel):
    character_person_id: int
    character_name: str
    role: InventoryAccessRole
    is_active_character: bool = False


class InventoryItemData(SQLModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: ItemCategory = ItemCategory.EQUIPMENT
    rarity: ItemRarity | None = None
    quantity: int = Field(default=1, ge=1)
    unit_value: MoneyAmount | None = None


class InventoryItemCreate(InventoryItemData):
    pass


class InventoryItemUpdate(SQLModel):
    """A partial item update suitable for a PATCH request."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: ItemCategory | None = None
    rarity: ItemRarity | None = None
    quantity: int | None = Field(default=None, ge=1)
    unit_value: MoneyAmount | None = None

    @field_validator("name", "description", "category", "quantity")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be cleared")
        return value


class InventoryItemRead(InventoryItemData):
    id: int
    total_value: MoneyAmount | None = None


class InventoryUpdate(SQLModel):
    """Editable inventory metadata; contents use their dedicated endpoints."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None

    @field_validator("name", "description")
    @classmethod
    def reject_explicit_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("This field cannot be cleared")
        return value


class InventoryRead(SQLModel):
    """The authoritative inventory returned by reads and all mutations."""

    id: int
    campaign_id: int
    name: str
    description: str = ""
    members: list[InventoryMemberRead] = Field(default_factory=list)
    purse: PurseRead
    items: list[InventoryItemRead] = Field(default_factory=list)
