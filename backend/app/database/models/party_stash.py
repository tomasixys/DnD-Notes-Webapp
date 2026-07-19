from typing import TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .campaign import Campaign


class CoinEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    value: int = 0
    type: str  # cp, sp, ep, gp, pp


class WealthLink(SQLModel, table=True):
    party_stash_id: int | None = Field(
        default=None,
        foreign_key="partystash.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    coin_entry_id: int | None = Field(
        default=None,
        foreign_key="coinentry.id",
        primary_key=True,
        ondelete="CASCADE",
    )


class LootItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    party_stash_id: int = Field(
        foreign_key="partystash.id",
        ondelete="CASCADE",
    )

    name: str
    desc: str = ""

    coin_entry_id: int | None = Field(
        default=None,
        foreign_key="coinentry.id",
        ondelete="SET NULL",
    )
    value: CoinEntry | None = Relationship()

    party_stash: "PartyStash" = Relationship(back_populates="loot")


class PartyStash(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(
        foreign_key="campaign.id",
        ondelete="CASCADE",
        unique=True,
    )

    campaign: "Campaign" = Relationship(back_populates="party_stash")

    coins: list[CoinEntry] = Relationship(
        link_model=WealthLink,
    )
    loot: list[LootItem] = Relationship(
        back_populates="party_stash",
        cascade_delete=True,
        passive_deletes=True,
    )
