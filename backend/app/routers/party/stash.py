from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.database.models import Campaign, PartyStash, LootItem, CoinEntry, WealthLink
from app.api.models import PartyStashRead, PartyStashUpdate, CoinEntryDto, TotalValueDto, WealthDto, LootItemRead


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/party/stash",
    tags=["party_stash"],
)


COIN_MULTIPLIER_TO_GP = {
    "cp": 0.01,
    "sp": 0.1,
    "ep": 0.5,
    "gp": 1.0,
    "pp": 10.0,
}


def get_or_create_party_stash(campaign_id: int, db: Session) -> PartyStash:
    statement = select(PartyStash).where(PartyStash.campaign_id == campaign_id)
    stash = db.exec(statement).first()

    if stash is None:
        stash = PartyStash(campaign_id=campaign_id)
        db.add(stash)
        db.commit()
        db.refresh(stash)

    return stash


def calculate_coins_total_gp(coins_list: list[CoinEntry]) -> float:
    return sum(
        coin.value * COIN_MULTIPLIER_TO_GP.get(coin.type, 0.0)
        for coin in coins_list
    )


@router.get("", response_model=PartyStashRead)
def get_party_stash(campaign_id: int, db: Session = Depends(get_session)):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    stash = get_or_create_party_stash(campaign_id, db)

    coins_dto_list = [
        CoinEntryDto(value=c.value, type=c.type) for c in stash.coins
    ]
    total_gp = calculate_coins_total_gp(stash.coins)

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


@router.put("", response_model=PartyStashRead)
def update_party_stash(
    campaign_id: int,
    payload: PartyStashUpdate,
    db: Session = Depends(get_session),
):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    stash = get_or_create_party_stash(campaign_id, db)

    # 1. Clean up old coins and loot items to prevent leaks/orphaned database entries.
    old_coins = list(stash.coins)
    old_loot = list(stash.loot)
    old_loot_coins = [item.value for item in old_loot if item.value]

    # Clear relationships
    stash.coins = []
    stash.loot = []
    db.flush()

    # Delete all old rows from database
    for coin in old_coins:
        db.delete(coin)
    for coin in old_loot_coins:
        db.delete(coin)
    db.flush()

    # 2. Add new coins to the wealth stash
    new_coins = []
    for coin_payload in payload.wealth.coins:
        db_coin = CoinEntry(
            value=coin_payload.value, type=coin_payload.type.value
        )
        db.add(db_coin)
        new_coins.append(db_coin)
    db.flush()
    stash.coins = new_coins

    # 3. Add new loot items and their custom values
    for item_payload in payload.loot:
        db_coin_val = CoinEntry(
            value=item_payload.value.value, type=item_payload.value.type.value
        )
        db.add(db_coin_val)
        db.flush()

        new_item = LootItem(
            party_stash_id=stash.id,
            name=item_payload.name,
            desc=item_payload.desc,
            coin_entry_id=db_coin_val.id,
        )
        db.add(new_item)

    db.add(stash)
    db.commit()
    db.refresh(stash)

    coins_dto_list = [
        CoinEntryDto(value=c.value, type=c.type) for c in stash.coins
    ]
    total_gp = calculate_coins_total_gp(stash.coins)

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
