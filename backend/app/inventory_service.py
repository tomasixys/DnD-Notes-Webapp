from decimal import Decimal

from sqlmodel import Session, select

from app.models.api import (
    InventoryItemRead,
    InventoryMemberRead,
    InventoryRead,
    MoneyAmount,
    PurseBalances,
    PurseRead,
)
from app.models.database import (
    Campaign,
    CharacterProfile,
    CurrencyBalance,
    Inventory,
    InventoryAccess,
    InventoryItem,
    Person,
    Purse,
)
from app.models.enums import (
    CurrencyDenomination,
    InventoryAccessRole,
)


COPPER_PER_GOLD = Decimal("100")


def money_to_copper(value: MoneyAmount) -> int:
    """Convert a public money value to the canonical integer copper amount."""

    copper = value.amount * value.denomination.value_in_gp * COPPER_PER_GOLD
    integral_copper = copper.to_integral_value()
    if copper != integral_copper:
        raise ValueError("Value must resolve to a whole number of copper pieces")
    return int(integral_copper)


def copper_to_money(value_cp: int) -> MoneyAmount:
    """Expose stored copper values as exact gold-relative decimal amounts."""

    return MoneyAmount(
        amount=Decimal(value_cp) / COPPER_PER_GOLD,
        denomination=CurrencyDenomination.GOLD,
    )


def _add_empty_purse(inventory_id: int, db: Session) -> None:
    db.add(Purse(inventory_id=inventory_id))
    db.add_all(
        [
            CurrencyBalance(
                purse_id=inventory_id,
                denomination=denomination,
                amount=0,
            )
            for denomination in CurrencyDenomination
        ]
    )


def _active_character_belongs_to_campaign(
    campaign: Campaign,
    db: Session,
) -> bool:
    person_id = campaign.active_character_person_id
    if person_id is None or db.get(CharacterProfile, person_id) is None:
        return False
    person = db.get(Person, person_id)
    return person is not None and person.campaign_id == campaign.id


def ensure_default_inventory(campaign: Campaign, db: Session) -> Inventory:
    """Return the campaign inventory, repairing missing required children."""

    inventory = db.exec(
        select(Inventory)
        .where(Inventory.campaign_id == campaign.id)
        .order_by(Inventory.id)
    ).first()
    if inventory is None:
        inventory = Inventory(campaign_id=campaign.id)
        db.add(inventory)
        db.flush()

    if db.get(Purse, inventory.id) is None:
        _add_empty_purse(inventory.id, db)
        db.flush()
    else:
        existing_denominations = set(
            db.exec(
                select(CurrencyBalance.denomination).where(
                    CurrencyBalance.purse_id == inventory.id
                )
            ).all()
        )
        missing_balances = [
            CurrencyBalance(
                purse_id=inventory.id,
                denomination=denomination,
                amount=0,
            )
            for denomination in CurrencyDenomination
            if denomination not in existing_denominations
        ]
        if missing_balances:
            db.add_all(missing_balances)
            db.flush()

    if (
        _active_character_belongs_to_campaign(campaign, db)
        and db.get(
            InventoryAccess,
            (inventory.id, campaign.active_character_person_id),
        )
        is None
    ):
        db.add(
            InventoryAccess(
                inventory_id=inventory.id,
                character_person_id=campaign.active_character_person_id,
                role=InventoryAccessRole.OWNER,
            )
        )
        db.flush()

    return inventory


def sync_default_inventory_owner(campaign: Campaign, db: Session) -> Inventory:
    """Make the current active character the sole automatic inventory owner."""

    inventory = ensure_default_inventory(campaign, db)
    grants = db.exec(
        select(InventoryAccess).where(
            InventoryAccess.inventory_id == inventory.id
        )
    ).all()
    for grant in grants:
        db.delete(grant)
    db.flush()

    if _active_character_belongs_to_campaign(campaign, db):
        db.add(
            InventoryAccess(
                inventory_id=inventory.id,
                character_person_id=campaign.active_character_person_id,
                role=InventoryAccessRole.OWNER,
            )
        )
        db.flush()
    return inventory


def inventory_to_read(
    inventory: Inventory,
    campaign: Campaign,
    db: Session,
) -> InventoryRead:
    balances_by_denomination = {
        balance.denomination: balance.amount
        for balance in db.exec(
            select(CurrencyBalance).where(
                CurrencyBalance.purse_id == inventory.id
            )
        ).all()
    }
    purse_balances = PurseBalances(
        **{
            denomination.value: balances_by_denomination.get(denomination, 0)
            for denomination in CurrencyDenomination
        }
    )
    purse_total_gp = sum(
        (
            Decimal(amount) * denomination.value_in_gp
            for denomination, amount in balances_by_denomination.items()
        ),
        start=Decimal("0"),
    )

    member_rows = db.exec(
        select(InventoryAccess, Person)
        .join(
            CharacterProfile,
            CharacterProfile.person_id == InventoryAccess.character_person_id,
        )
        .join(Person, Person.id == CharacterProfile.person_id)
        .where(InventoryAccess.inventory_id == inventory.id)
        .order_by(Person.name, Person.id)
    ).all()
    members = [
        InventoryMemberRead(
            character_person_id=person.id,
            character_name=person.name,
            role=grant.role,
            is_active_character=(
                campaign.active_character_person_id == person.id
            ),
        )
        for grant, person in member_rows
    ]

    stored_items = db.exec(
        select(InventoryItem)
        .where(InventoryItem.inventory_id == inventory.id)
        .order_by(InventoryItem.id)
    ).all()
    items = [
        InventoryItemRead(
            id=item.id,
            name=item.name,
            description=item.description,
            category=item.category,
            rarity=item.rarity,
            quantity=item.quantity,
            unit_value=(
                copper_to_money(item.unit_value_cp)
                if item.unit_value_cp is not None
                else None
            ),
            total_value=(
                copper_to_money(item.unit_value_cp * item.quantity)
                if item.unit_value_cp is not None
                else None
            ),
        )
        for item in stored_items
    ]

    return InventoryRead(
        id=inventory.id,
        campaign_id=campaign.id,
        name=inventory.name,
        description=inventory.description,
        members=members,
        purse=PurseRead(
            balances=purse_balances,
            total_value=MoneyAmount(
                amount=purse_total_gp,
                denomination=CurrencyDenomination.GOLD,
            ),
        ),
        items=items,
    )
