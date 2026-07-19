from fastapi import Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.database import Campaign, PartyStash, LootItem, CoinEntry
from app.models.enums import CoinType
from app.models.api import (
    PartyStashCreate,
    PartyStashRead,
    PartyStashUpdate,
    CoinEntryDto,
    TotalValueDto,
    WealthDto,
    LootItemRead,
    LootItemUpdate,
)

COIN_MULTIPLIER_TO_GP: dict[CoinType, float] = {
    CoinType.CP: 0.01,
    CoinType.SP: 0.1,
    CoinType.EP: 0.5,
    CoinType.GP: 1.0,
    CoinType.PP: 10.0,
}


def _default_stash_read() -> PartyStashRead:
    """Return an empty stash DTO with no id (nothing persisted yet)."""
    return PartyStashRead(
        id=None,
        wealth=WealthDto(
            coins=[],
            total_value=TotalValueDto(value=0.0, type=CoinType.GP),
        ),
        loot=[],
    )


class StashService:
    def __init__(self, db: Session = Depends(get_session)):
        self.db = db

    # ── Private helpers ─────────────────────────────────────────────

    def _verify_campaign(self, campaign_id: int) -> Campaign:
        campaign = self.db.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return campaign

    def _get_stash(self, campaign_id: int) -> PartyStash | None:
        statement = select(PartyStash).where(PartyStash.campaign_id == campaign_id)
        return self.db.exec(statement).first()

    def _ensure_stash(self, campaign_id: int) -> PartyStash:
        """Return an existing stash or create an empty one."""
        stash = self._get_stash(campaign_id)
        if stash is None:
            stash = PartyStash(campaign_id=campaign_id)
            self.db.add(stash)
            self.db.commit()
            self.db.refresh(stash)
        return stash

    def _require_stash(self, campaign_id: int) -> PartyStash:
        """Return an existing stash or raise 404."""
        stash = self._get_stash(campaign_id)
        if stash is None:
            raise HTTPException(status_code=404, detail="Party stash not found")
        return stash

    @staticmethod
    def _to_loot_item_read(item: LootItem) -> LootItemRead:
        if item.value:
            value_dto = CoinEntryDto(value=item.value.value, type=item.value.type)
        else:
            value_dto = CoinEntryDto(value=0, type=CoinType.GP)

        return LootItemRead(
            id=item.id,
            name=item.name,
            desc=item.desc,
            value=value_dto,
        )

    def _to_stash_read(self, stash: PartyStash) -> PartyStashRead:
        coins_dto = [
            CoinEntryDto(value=c.value, type=c.type) for c in stash.coins
        ]
        total_gp = self.calculate_coins_total_gp(stash.coins)

        return PartyStashRead(
            id=stash.id,
            wealth=WealthDto(
                coins=coins_dto,
                total_value=TotalValueDto(value=total_gp, type=CoinType.GP),
            ),
            loot=[self._to_loot_item_read(item) for item in stash.loot],
        )

    def _apply_stash_payload(
        self,
        stash: PartyStash,
        payload: PartyStashCreate | PartyStashUpdate,
    ) -> None:
        """Replace the coins and loot on a stash with the payload data."""
        stash_id = stash.id
        if stash_id is None:
            raise RuntimeError("Cannot apply payload to a stash without an id")

        # Collect orphans before unlinking
        old_coins = list(stash.coins)
        old_loot = list(stash.loot)
        old_loot_coins = [item.value for item in old_loot if item.value]

        # Unlink
        stash.coins = []
        stash.loot = []
        self.db.flush()

        # Delete orphaned rows
        for coin in old_coins:
            self.db.delete(coin)
        for coin in old_loot_coins:
            self.db.delete(coin)
        self.db.flush()

        # Create new coins
        new_coins = []
        for coin_payload in payload.wealth.coins:
            db_coin = CoinEntry(
                value=coin_payload.value, type=coin_payload.type.value
            )
            self.db.add(db_coin)
            new_coins.append(db_coin)
        self.db.flush()
        stash.coins = new_coins

        # Create new loot items
        for item_payload in payload.loot:
            db_coin_val = CoinEntry(
                value=item_payload.value.value, type=item_payload.value.type.value
            )
            self.db.add(db_coin_val)
            self.db.flush()

            new_item = LootItem(
                party_stash_id=stash_id,
                name=item_payload.name,
                desc=item_payload.desc,
                coin_entry_id=db_coin_val.id,
            )
            self.db.add(new_item)

        self.db.add(stash)
        self.db.commit()
        self.db.refresh(stash)

    # ── Public API ──────────────────────────────────────────────────

    @staticmethod
    def calculate_coins_total_gp(coins_list: list[CoinEntry]) -> float:
        return sum(
            coin.value * COIN_MULTIPLIER_TO_GP.get(CoinType(coin.type), 0.0)
            for coin in coins_list
        )

    def get_stash(self, campaign_id: int) -> PartyStashRead:
        """Return the stash for a campaign, or an empty default if none exists."""
        self._verify_campaign(campaign_id)

        stash = self._get_stash(campaign_id)
        if stash is None:
            return _default_stash_read()

        return self._to_stash_read(stash)

    def create_stash(self, campaign_id: int, payload: PartyStashCreate) -> PartyStashRead:
        """Create or reset a party stash for a campaign."""
        self._verify_campaign(campaign_id)

        stash = self._ensure_stash(campaign_id)
        self._apply_stash_payload(stash, payload)
        return self._to_stash_read(stash)

    def update_stash(self, campaign_id: int, payload: PartyStashUpdate) -> PartyStashRead:
        """Update an existing party stash. 404 if none exists."""
        self._verify_campaign(campaign_id)

        stash = self._require_stash(campaign_id)
        self._apply_stash_payload(stash, payload)
        return self._to_stash_read(stash)

    def add_loot_item(self, campaign_id: int, payload: LootItemUpdate) -> LootItemRead:
        """Add a loot item, auto-creating the stash if needed."""
        self._verify_campaign(campaign_id)

        stash = self._ensure_stash(campaign_id)
        stash_id = stash.id
        if stash_id is None:
            raise RuntimeError("Stash id must not be None after ensure")

        db_coin_val = CoinEntry(
            value=payload.value.value, type=payload.value.type.value
        )
        self.db.add(db_coin_val)
        self.db.flush()

        new_item = LootItem(
            party_stash_id=stash_id,
            name=payload.name,
            desc=payload.desc,
            coin_entry_id=db_coin_val.id,
        )
        self.db.add(new_item)
        self.db.commit()
        self.db.refresh(new_item)

        return self._to_loot_item_read(new_item)

    def delete_loot_item(self, campaign_id: int, loot_id: int) -> None:
        """Delete a loot item from the stash. 404 if stash or item not found."""
        self._verify_campaign(campaign_id)

        stash = self._require_stash(campaign_id)

        item = self.db.get(LootItem, loot_id)
        if item is None or item.party_stash_id != stash.id:
            raise HTTPException(status_code=404, detail="Loot item not found")

        coin_entry = item.value

        self.db.delete(item)
        self.db.flush()

        if coin_entry:
            self.db.delete(coin_entry)
            self.db.flush()

        self.db.commit()
