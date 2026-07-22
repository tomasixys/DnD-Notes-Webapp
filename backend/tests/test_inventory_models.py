import sqlite3
import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.migrations import CURRENT_DATABASE_VERSION, run_database_migrations
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
    CURRENCY_VALUES_IN_GP,
    CurrencyDenomination,
    InventoryAccessRole,
    ItemCategory,
    ItemRarity,
)


class InventoryModelTests(unittest.TestCase):
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

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _add_character(db: Session, campaign_id: int, name: str) -> CharacterProfile:
        person = Person(campaign_id=campaign_id, name=name)
        db.add(person)
        db.flush()
        profile = CharacterProfile(person_id=person.id)
        db.add(profile)
        db.flush()
        return profile

    def test_inventory_groups_purse_items_and_role_based_character_access(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.flush()

            owner = self._add_character(db, campaign.id, "Nalia")
            manager = self._add_character(db, campaign.id, "Sable")
            campaign.active_character_person_id = owner.person_id

            inventory = Inventory(
                campaign_id=campaign.id,
                name="Shared Pack",
            )
            db.add(inventory)
            db.flush()

            purse = Purse(inventory_id=inventory.id)
            db.add(purse)
            db.add_all(
                [
                    CurrencyBalance(
                        purse_id=inventory.id,
                        denomination=denomination,
                        amount=amount,
                    )
                    for denomination, amount in (
                        (CurrencyDenomination.COPPER, 12),
                        (CurrencyDenomination.SILVER, 8),
                        (CurrencyDenomination.ELECTRUM, 0),
                        (CurrencyDenomination.GOLD, 42),
                        (CurrencyDenomination.PLATINUM, 2),
                    )
                ]
            )
            db.add_all(
                [
                    InventoryAccess(
                        inventory_id=inventory.id,
                        character_person_id=owner.person_id,
                        role=InventoryAccessRole.OWNER,
                    ),
                    InventoryAccess(
                        inventory_id=inventory.id,
                        character_person_id=manager.person_id,
                        role=InventoryAccessRole.MANAGER,
                    ),
                    InventoryItem(
                        inventory_id=inventory.id,
                        name="Rope",
                        category=ItemCategory.EQUIPMENT,
                        quantity=2,
                        unit_value_cp=100,
                    ),
                    InventoryItem(
                        inventory_id=inventory.id,
                        name="Healing Potion",
                        category=ItemCategory.CONSUMABLE,
                        rarity=ItemRarity.UNCOMMON,
                        quantity=3,
                        unit_value_cp=5000,
                    ),
                    InventoryItem(
                        inventory_id=inventory.id,
                        name="Sapphire",
                        category=ItemCategory.VALUABLE,
                        rarity=ItemRarity.RARE,
                        unit_value_cp=10000,
                    ),
                ]
            )
            db.commit()
            db.expire_all()

            stored = db.get(Inventory, inventory.id)
            self.assertEqual(stored.campaign.name, "Test")
            self.assertEqual(stored.purse.inventory_id, stored.id)
            self.assertEqual(
                {
                    balance.denomination: balance.amount
                    for balance in stored.purse.balances
                },
                {
                    CurrencyDenomination.COPPER: 12,
                    CurrencyDenomination.SILVER: 8,
                    CurrencyDenomination.ELECTRUM: 0,
                    CurrencyDenomination.GOLD: 42,
                    CurrencyDenomination.PLATINUM: 2,
                },
            )
            self.assertEqual(
                {
                    grant.character_profile.person.name: grant.role
                    for grant in stored.access_grants
                },
                {
                    "Nalia": InventoryAccessRole.OWNER,
                    "Sable": InventoryAccessRole.MANAGER,
                },
            )
            self.assertEqual(
                {
                    item.name: (item.category, item.rarity)
                    for item in stored.items
                },
                {
                    "Rope": (ItemCategory.EQUIPMENT, None),
                    "Healing Potion": (
                        ItemCategory.CONSUMABLE,
                        ItemRarity.UNCOMMON,
                    ),
                    "Sapphire": (
                        ItemCategory.VALUABLE,
                        ItemRarity.RARE,
                    ),
                },
            )

    def test_currency_values_use_exact_gold_relative_decimals(self):
        expected_values = {
            CurrencyDenomination.COPPER: Decimal("0.01"),
            CurrencyDenomination.SILVER: Decimal("0.1"),
            CurrencyDenomination.ELECTRUM: Decimal("0.5"),
            CurrencyDenomination.GOLD: Decimal("1"),
            CurrencyDenomination.PLATINUM: Decimal("10"),
        }

        self.assertEqual(CURRENCY_VALUES_IN_GP, expected_values)
        self.assertEqual(
            {
                denomination: denomination.value_in_gp
                for denomination in CurrencyDenomination
            },
            expected_values,
        )

    def test_character_and_campaign_deletes_follow_ownership_boundaries(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.flush()
            owner = self._add_character(db, campaign.id, "Nalia")
            campaign.active_character_person_id = owner.person_id

            inventory = Inventory(campaign_id=campaign.id)
            db.add(inventory)
            db.flush()
            db.add(Purse(inventory_id=inventory.id))
            db.add(
                CurrencyBalance(
                    purse_id=inventory.id,
                    denomination=CurrencyDenomination.GOLD,
                    amount=10,
                )
            )
            db.add(
                InventoryItem(
                    inventory_id=inventory.id,
                    name="Rope",
                )
            )
            db.add(
                InventoryAccess(
                    inventory_id=inventory.id,
                    character_person_id=owner.person_id,
                )
            )
            db.commit()
            inventory_id = inventory.id

            db.delete(owner)
            db.commit()
            db.expire_all()

            self.assertIsNotNone(db.get(Inventory, inventory_id))
            self.assertEqual(db.exec(select(InventoryAccess)).all(), [])
            db.refresh(campaign)
            self.assertIsNone(campaign.active_character_person_id)

            db.delete(campaign)
            db.commit()
            self.assertIsNone(db.get(Inventory, inventory_id))
            self.assertEqual(db.exec(select(Purse)).all(), [])
            self.assertEqual(db.exec(select(CurrencyBalance)).all(), [])
            self.assertEqual(db.exec(select(InventoryItem)).all(), [])

    def test_currency_and_item_amounts_are_constrained(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.flush()
            inventory = Inventory(campaign_id=campaign.id)
            db.add(inventory)
            db.flush()
            db.add(Purse(inventory_id=inventory.id))
            db.commit()

            db.add(
                CurrencyBalance(
                    purse_id=inventory.id,
                    denomination=CurrencyDenomination.GOLD,
                    amount=-1,
                )
            )
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            db.add(
                InventoryItem(
                    inventory_id=inventory.id,
                    name="Invalid stack",
                    quantity=0,
                )
            )
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            db.add(
                InventoryItem(
                    inventory_id=inventory.id,
                    name="Invalid value",
                    unit_value_cp=-1,
                )
            )
            with self.assertRaises(IntegrityError):
                db.commit()


class InventoryMigrationTests(unittest.TestCase):
    def test_development_migration_adds_inventory_schema_idempotently(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "version-three.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE campaign (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL
                    );
                    CREATE TABLE person (
                        id INTEGER PRIMARY KEY,
                        campaign_id INTEGER NOT NULL,
                        name TEXT NOT NULL
                    );
                    CREATE TABLE characterprofile (
                        person_id INTEGER PRIMARY KEY,
                        short_bio TEXT NOT NULL DEFAULT '',
                        appearance TEXT NOT NULL DEFAULT '',
                        image_path TEXT NOT NULL DEFAULT '',
                        FOREIGN KEY(person_id) REFERENCES person (id) ON DELETE CASCADE
                    );
                    CREATE TABLE inventory (
                        id INTEGER PRIMARY KEY,
                        campaign_id INTEGER NOT NULL,
                        name TEXT NOT NULL DEFAULT 'Party Inventory',
                        description TEXT NOT NULL DEFAULT ''
                    );
                    CREATE TABLE inventoryitem (
                        id INTEGER PRIMARY KEY,
                        inventory_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        category TEXT NOT NULL DEFAULT 'equipment',
                        quantity INTEGER NOT NULL DEFAULT 1,
                        unit_value_cp INTEGER
                    );
                    CREATE TABLE currencyvalue (
                        denomination TEXT PRIMARY KEY,
                        value_in_gp NUMERIC NOT NULL
                    );
                    INSERT INTO currencyvalue VALUES ('gp', 1);
                    PRAGMA user_version = 3;
                    """
                )
                connection.commit()

            engine = create_engine(
                f"sqlite:///{database_path}",
                poolclass=NullPool,
            )
            run_database_migrations(engine)
            run_database_migrations(engine)

            schema = inspect(engine)
            table_names = set(schema.get_table_names())
            with engine.connect() as connection:
                version = connection.exec_driver_sql(
                    "PRAGMA user_version"
                ).scalar_one()
            engine.dispose()

            self.assertEqual(version, CURRENT_DATABASE_VERSION)
            self.assertTrue(
                {
                    "inventory",
                    "inventoryaccess",
                    "purse",
                    "currencybalance",
                    "inventoryitem",
                }.issubset(table_names)
            )
            self.assertNotIn("currencyvalue", table_names)

            inventory_columns = {
                column["name"] for column in schema.get_columns("inventory")
            }
            item_columns = {
                column["name"] for column in schema.get_columns("inventoryitem")
            }
            balance_primary_key = set(
                schema.get_pk_constraint("currencybalance")["constrained_columns"]
            )
            access_primary_key = set(
                schema.get_pk_constraint("inventoryaccess")["constrained_columns"]
            )

            self.assertEqual(
                inventory_columns,
                {"id", "campaign_id", "name", "description"},
            )
            self.assertTrue(
                {
                    "id",
                    "inventory_id",
                    "name",
                    "description",
                    "category",
                    "rarity",
                    "quantity",
                    "unit_value_cp",
                }.issubset(item_columns)
            )
            self.assertEqual(
                balance_primary_key,
                {"purse_id", "denomination"},
            )
            self.assertEqual(
                access_primary_key,
                {"inventory_id", "character_person_id"},
            )
if __name__ == "__main__":
    unittest.main()
