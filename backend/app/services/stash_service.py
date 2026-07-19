from fastapi import Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.database import Campaign, PartyStash, LootItem, CoinEntry
from app.models.api import (
    PartyStashUpdate,
    CoinEntryDto,
    LootItemUpdate,
)

COIN_MULTIPLIER_TO_GP = {
    "cp": 0.01,
    "sp": 0.1,
    "ep": 0.5,
    "gp": 1.0,
    "pp": 10.0,
}


class StashService:
    def __init__(self, db: Session = Depends(get_session)):
        self.db = db

    def get_or_create_party_stash(self, campaign_id: int) -> PartyStash:
        statement = select(PartyStash).where(PartyStash.campaign_id == campaign_id)
        stash = self.db.exec(statement).first()

        if stash is None:
            stash = PartyStash(campaign_id=campaign_id)
            self.db.add(stash)
            self.db.commit()
            self.db.refresh(stash)

        return stash

    def calculate_coins_total_gp(self, coins_list: list[CoinEntry]) -> float:
        return sum(
            coin.value * COIN_MULTIPLIER_TO_GP.get(coin.type, 0.0)
            for coin in coins_list
        )

    def get_stash(self, campaign_id: int) -> dict:
        campaign = self.db.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")

        stash = self.get_or_create_party_stash(campaign_id)

        coins_dto_list = [
            CoinEntryDto(value=c.value, type=c.type) for c in stash.coins
        ]
        total_gp = self.calculate_coins_total_gp(stash.coins)

        return {
            "wealth": {
                "coins": coins_dto_list,
                "total_value": {
                    "value": total_gp,
                    "type": "gp",
                },
            },
            "loot": [
                {
                    "id": item.id,
                    "name": item.name,
                    "desc": item.desc,
                    "value": (
                        CoinEntryDto(value=item.value.value, type=item.value.type)
                        if item.value
                        else CoinEntryDto(value=0, type="gp")
                    ),
                }
                for item in stash.loot
            ],
        }

    def update_stash(self, campaign_id: int, payload: PartyStashUpdate) -> dict:
        campaign = self.db.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")

        stash = self.get_or_create_party_stash(campaign_id)

        old_coins = list(stash.coins)
        old_loot = list(stash.loot)
        old_loot_coins = [item.value for item in old_loot if item.value]

        stash.coins = []
        stash.loot = []
        self.db.flush()

        for coin in old_coins:
            self.db.delete(coin)
        for coin in old_loot_coins:
            self.db.delete(coin)
        self.db.flush()

        new_coins = []
        for coin_payload in payload.wealth.coins:
            db_coin = CoinEntry(
                value=coin_payload.value, type=coin_payload.type.value
            )
            self.db.add(db_coin)
            new_coins.append(db_coin)
        self.db.flush()
        stash.coins = new_coins

        for item_payload in payload.loot:
            db_coin_val = CoinEntry(
                value=item_payload.value.value, type=item_payload.value.type.value
            )
            self.db.add(db_coin_val)
            self.db.flush()

            new_item = LootItem(
                party_stash_id=stash.id,
                name=item_payload.name,
                desc=item_payload.desc,
                coin_entry_id=db_coin_val.id,
            )
            self.db.add(new_item)

        self.db.add(stash)
        self.db.commit()
        self.db.refresh(stash)

        coins_dto_list = [
            CoinEntryDto(value=c.value, type=c.type) for c in stash.coins
        ]
        total_gp = self.calculate_coins_total_gp(stash.coins)

        return {
            "wealth": {
                "coins": coins_dto_list,
                "total_value": {
                    "value": total_gp,
                    "type": "gp",
                },
            },
            "loot": [
                {
                    "id": item.id,
                    "name": item.name,
                    "desc": item.desc,
                    "value": (
                        CoinEntryDto(value=item.value.value, type=item.value.type)
                        if item.value
                        else CoinEntryDto(value=0, type="gp")
                    ),
                }
                for item in stash.loot
            ],
        }

    def add_loot_item(self, campaign_id: int, payload: LootItemUpdate) -> dict:
        campaign = self.db.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")

        stash = self.get_or_create_party_stash(campaign_id)

        db_coin_val = CoinEntry(
            value=payload.value.value, type=payload.value.type.value
        )
        self.db.add(db_coin_val)
        self.db.flush()

        new_item = LootItem(
            party_stash_id=stash.id,
            name=payload.name,
            desc=payload.desc,
            coin_entry_id=db_coin_val.id,
        )
        self.db.add(new_item)
        self.db.commit()
        self.db.refresh(new_item)

        return {
            "id": new_item.id,
            "name": new_item.name,
            "desc": new_item.desc,
            "value": CoinEntryDto(value=new_item.value.value, type=new_item.value.type)
            if new_item.value
            else CoinEntryDto(value=0, type="gp"),
        }

    def delete_loot_item(self, campaign_id: int, loot_id: int) -> dict:
        campaign = self.db.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")

        stash = self.get_or_create_party_stash(campaign_id)

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
        return {"success": True}
