import unittest

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.api import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryUpdate,
    PurseBalancesUpdate,
    PurseUpdate,
)
from app.models.database import Campaign, Inventory, InventoryItem
from app.services.campaign_context import CampaignContext
from app.services.inventory import InventoryService


class InventoryServiceTests(unittest.TestCase):
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

    def test_stage_operations_participate_in_the_outer_transaction(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            inventory_service = InventoryService(
                CampaignContext(db, campaign)
            )

            inventory = inventory_service.stage_update_metadata(
                InventoryUpdate(name="Shared Pack"),
            )
            inventory_service.stage_update_purse(
                PurseUpdate(
                    balances=PurseBalancesUpdate(gp=42),
                ),
            )
            inventory_service.stage_create_item(
                InventoryItemCreate(name="Rope"),
            )
            inventory_id = inventory.id
            item_id = db.exec(select(InventoryItem)).one().id

            self.assertEqual("Shared Pack", inventory.name)
            self.assertIsNotNone(db.get(InventoryItem, item_id))

            db.rollback()
            self.assertIsNone(db.get(Inventory, inventory_id))
            self.assertIsNone(db.get(InventoryItem, item_id))

    def test_standalone_mutations_commit_and_return_the_aggregate(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            inventory_service = InventoryService(
                CampaignContext(db, campaign)
            )

            created = inventory_service.create_item(
                InventoryItemCreate(name="Rope", quantity=2),
            )
            item_id = created.items[0].id

            updated = inventory_service.update_item(
                item_id,
                InventoryItemUpdate(quantity=3),
            )
            self.assertEqual(3, updated.items[0].quantity)
            self.assertIsNotNone(db.get(InventoryItem, item_id))

            deleted = inventory_service.delete_item(item_id)
            self.assertEqual([], deleted.items)
            self.assertIsNone(db.get(InventoryItem, item_id))

    def test_standalone_validation_failure_rolls_back_repairs(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            with self.assertRaises(HTTPException):
                InventoryService(
                    CampaignContext(db, campaign)
                ).update_metadata(
                    InventoryUpdate(name="   "),
                )

            self.assertEqual([], db.exec(select(Inventory)).all())


if __name__ == "__main__":
    unittest.main()
