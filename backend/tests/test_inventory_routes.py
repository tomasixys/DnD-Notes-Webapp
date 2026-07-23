import unittest
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.api import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryRead,
    InventoryUpdate,
    MoneyAmount,
    PurseBalancesUpdate,
    PurseUpdate,
)
from app.models.database import (
    Campaign,
    CharacterProfile,
    InventoryItem,
    Person,
)
from app.models.enums import (
    CurrencyDenomination,
    ItemCategory,
    ItemRarity,
)
from app.routers.characters import activate_character
from app.routers.inventory import (
    create_inventory_item,
    delete_inventory_item,
    get_inventory,
    router,
    update_inventory,
    update_inventory_item,
    update_purse,
)


class InventoryRouteIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.flush()
            person = Person(campaign_id=campaign.id, name="Nalia")
            db.add(person)
            db.flush()
            db.add(CharacterProfile(person_id=person.id))
            db.flush()
            campaign.active_character_person_id = person.id
            db.add(campaign)
            db.commit()
            self.campaign_id = campaign.id
            self.owner_id = person.id

    def tearDown(self):
        self.engine.dispose()

    def test_inventory_mutations_return_the_complete_updated_inventory(self):
        with Session(self.engine) as db:
            initial = get_inventory(self.campaign_id, db)
            self.assertEqual(initial.name, "Party Inventory")
            self.assertEqual(
                initial.purse.balances.model_dump(),
                {"cp": 0, "sp": 0, "ep": 0, "gp": 0, "pp": 0},
            )
            self.assertEqual(len(initial.members), 1)
            self.assertEqual(initial.members[0].character_person_id, self.owner_id)
            self.assertTrue(initial.members[0].is_active_character)

            renamed = update_inventory(
                self.campaign_id,
                InventoryUpdate(
                    name="Shared Pack",
                    description="Party supplies",
                ),
                db,
            )
            self.assertEqual(renamed.name, "Shared Pack")

            purse_payload = update_purse(
                self.campaign_id,
                PurseUpdate(
                    balances=PurseBalancesUpdate(sp=8, gp=42)
                ),
                db,
            )
            self.assertEqual(purse_payload.purse.balances.sp, 8)
            self.assertEqual(purse_payload.purse.total_value.amount, Decimal("42.8"))

            created_payload = create_inventory_item(
                self.campaign_id,
                InventoryItemCreate(
                    name="Healing Potion",
                    category=ItemCategory.CONSUMABLE,
                    rarity=ItemRarity.UNCOMMON,
                    quantity=3,
                    unit_value=MoneyAmount(
                        amount=Decimal("0.5"),
                        denomination=CurrencyDenomination.PLATINUM,
                    ),
                ),
                db,
            )
            item = created_payload.items[0]
            item_id = item.id
            self.assertEqual(item.unit_value.amount, Decimal("5"))
            self.assertEqual(item.total_value.amount, Decimal("15"))

            stored_item = db.get(InventoryItem, item_id)
            self.assertEqual(stored_item.unit_value_cp, 500)

            updated_payload = update_inventory_item(
                self.campaign_id,
                item_id,
                InventoryItemUpdate(
                    quantity=2,
                    rarity=None,
                    unit_value=None,
                ),
                db,
            )
            updated_item = updated_payload.items[0]
            self.assertEqual(updated_item.quantity, 2)
            self.assertIsNone(updated_item.rarity)
            self.assertIsNone(updated_item.unit_value)
            self.assertIsNone(updated_item.total_value)

            deleted_payload = delete_inventory_item(
                self.campaign_id,
                item_id,
                db,
            )
            self.assertEqual(deleted_payload.items, [])
            self.assertEqual(deleted_payload.purse.balances.gp, 42)
            self.assertIsNone(db.get(InventoryItem, item_id))

    def test_item_value_must_resolve_to_whole_copper(self):
        with Session(self.engine) as db:
            with self.assertRaises(HTTPException) as context:
                create_inventory_item(
                    self.campaign_id,
                    InventoryItemCreate(
                        name="Impossible fraction",
                        unit_value=MoneyAmount(
                            amount=Decimal("0.5"),
                            denomination=CurrencyDenomination.COPPER,
                        ),
                    ),
                    db,
                )
            self.assertEqual(context.exception.status_code, 422)
            self.assertIn("whole number of copper", context.exception.detail)
            self.assertEqual(db.exec(select(InventoryItem)).all(), [])

    def test_activating_character_transfers_automatic_ownership(self):
        with Session(self.engine) as db:
            get_inventory(self.campaign_id, db)
            person = Person(campaign_id=self.campaign_id, name="Sable")
            db.add(person)
            db.flush()
            db.add(CharacterProfile(person_id=person.id))
            db.commit()
            replacement_id = person.id

            activate_character(self.campaign_id, replacement_id, db)
            response = get_inventory(self.campaign_id, db)
            self.assertEqual(len(response.members), 1)
            self.assertEqual(
                response.members[0].character_person_id,
                replacement_id,
            )
            self.assertTrue(response.members[0].is_active_character)

    def test_router_registers_full_inventory_responses_for_every_mutation(self):
        route_contracts = {
            (route.path, next(iter(route.methods))): route.response_model
            for route in router.routes
        }

        expected_routes = {
            ("/api/campaigns/{campaign_id}/inventory", "GET"),
            ("/api/campaigns/{campaign_id}/inventory", "PATCH"),
            ("/api/campaigns/{campaign_id}/inventory/purse", "PATCH"),
            ("/api/campaigns/{campaign_id}/inventory/items", "POST"),
            (
                "/api/campaigns/{campaign_id}/inventory/items/{item_id}",
                "PATCH",
            ),
            (
                "/api/campaigns/{campaign_id}/inventory/items/{item_id}",
                "DELETE",
            ),
        }
        self.assertTrue(expected_routes.issubset(route_contracts))
        for route_key in expected_routes:
            self.assertIs(route_contracts[route_key], InventoryRead)


if __name__ == "__main__":
    unittest.main()
