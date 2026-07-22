import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.models.api import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMemberRead,
    InventoryRead,
    MoneyAmount,
    PurseBalances,
    PurseBalancesUpdate,
    PurseRead,
    PurseUpdate,
)
from app.models.enums import (
    CurrencyDenomination,
    InventoryAccessRole,
    ItemCategory,
    ItemRarity,
)


class InventoryApiModelTests(unittest.TestCase):
    def test_inventory_read_serializes_as_one_composed_response(self):
        inventory = InventoryRead(
            id=7,
            campaign_id=3,
            name="Party Inventory",
            members=[
                InventoryMemberRead(
                    character_person_id=11,
                    character_name="Nalia",
                    role=InventoryAccessRole.OWNER,
                    is_active_character=True,
                )
            ],
            purse=PurseRead(
                balances=PurseBalances(cp=12, sp=8, gp=42, pp=2),
                total_value=MoneyAmount(
                    amount=Decimal("62.92"),
                    denomination=CurrencyDenomination.GOLD,
                ),
            ),
            items=[
                InventoryItemRead(
                    id=21,
                    name="Healing Potion",
                    category=ItemCategory.CONSUMABLE,
                    rarity=ItemRarity.UNCOMMON,
                    quantity=3,
                    unit_value=MoneyAmount(
                        amount=Decimal("50"),
                        denomination=CurrencyDenomination.GOLD,
                    ),
                    total_value=MoneyAmount(
                        amount=Decimal("150"),
                        denomination=CurrencyDenomination.GOLD,
                    ),
                )
            ],
        )

        payload = inventory.model_dump(mode="json")

        self.assertEqual(payload["id"], 7)
        self.assertEqual(payload["members"][0]["role"], "owner")
        self.assertEqual(payload["purse"]["balances"]["ep"], 0)
        self.assertEqual(payload["purse"]["total_value"]["amount"], "62.92")
        self.assertEqual(payload["items"][0]["rarity"], "uncommon")
        self.assertEqual(payload["items"][0]["unit_value"]["amount"], "50")

    def test_purse_update_only_contains_changed_denominations(self):
        update = PurseUpdate(balances=PurseBalancesUpdate(gp=43))

        self.assertEqual(
            update.model_dump(exclude_none=True, mode="json"),
            {"balances": {"gp": 43}},
        )
        self.assertEqual(update.balances.model_fields_set, {"gp"})

    def test_item_update_distinguishes_omitted_and_cleared_values(self):
        unchanged = InventoryItemUpdate()
        clear_optional_values = InventoryItemUpdate(
            rarity=None,
            unit_value=None,
        )

        self.assertEqual(unchanged.model_fields_set, set())
        self.assertEqual(
            clear_optional_values.model_fields_set,
            {"rarity", "unit_value"},
        )

    def test_request_models_reject_invalid_amounts(self):
        invalid_models = (
            lambda: MoneyAmount(amount=Decimal("-0.01")),
            lambda: PurseBalances(gp=-1),
            lambda: PurseBalancesUpdate(sp=-1),
            lambda: PurseBalancesUpdate(sp=None),
            lambda: InventoryItemCreate(name="", quantity=1),
            lambda: InventoryItemCreate(name="Rope", quantity=0),
            lambda: InventoryItemUpdate(name=None),
        )

        for create_invalid_model in invalid_models:
            with self.subTest(model=create_invalid_model):
                with self.assertRaises(ValidationError):
                    create_invalid_model()


if __name__ == "__main__":
    unittest.main()
