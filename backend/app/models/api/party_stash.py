from sqlmodel import Field, SQLModel
from app.models.enums import CoinType


class CoinEntryDto(SQLModel):
    value: int
    type: CoinType


class TotalValueDto(SQLModel):
    value: float
    type: CoinType = CoinType.GP


class WealthDto(SQLModel):
    coins: list[CoinEntryDto] = Field(default_factory=list)
    total_value: TotalValueDto


class LootItemRead(SQLModel):
    id: int
    name: str
    desc: str = ""
    value: CoinEntryDto


class PartyStashRead(SQLModel):
    id: int | None = None
    wealth: WealthDto
    loot: list[LootItemRead] = Field(default_factory=list)


class LootItemUpdate(SQLModel):
    name: str
    desc: str = ""
    value: CoinEntryDto


class PartyStashCreate(SQLModel):
    wealth: WealthDto
    loot: list[LootItemUpdate] = Field(default_factory=list)


class PartyStashUpdate(SQLModel):
    wealth: WealthDto
    loot: list[LootItemUpdate] = Field(default_factory=list)
