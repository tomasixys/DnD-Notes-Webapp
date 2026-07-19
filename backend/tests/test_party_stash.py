import unittest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.database import Campaign
from app.models.api import (
    PartyStashCreate,
    PartyStashUpdate,
    WealthDto,
    CoinEntryDto,
    LootItemUpdate,
)
from app.services.stash_service import StashService


class PartyStashIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        from sqlalchemy import event

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)

    def _make_service(self) -> tuple[Session, StashService, int]:
        """Create a DB session, a service, and a campaign, returning all three."""
        db = Session(self.engine)
        campaign = Campaign(name="Fellowship")
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        service = StashService(db)
        return db, service, campaign.id

    # ── GET behaviour ───────────────────────────────────────────────

    def test_get_returns_empty_stash_with_no_id_when_none_exists(self):
        db, service, campaign_id = self._make_service()
        try:
            stash = service.get_stash(campaign_id)

            self.assertIsNone(stash.id)
            self.assertEqual(len(stash.wealth.coins), 0)
            self.assertEqual(stash.wealth.total_value.value, 0.0)
            self.assertEqual(stash.wealth.total_value.type, "gp")
            self.assertEqual(len(stash.loot), 0)
        finally:
            db.close()

    def test_get_does_not_create_db_row(self):
        db, service, campaign_id = self._make_service()
        try:
            service.get_stash(campaign_id)

            # Verify nothing was persisted
            from app.models.database import PartyStash

            stash = service._get_stash(campaign_id)
            self.assertIsNone(stash)
        finally:
            db.close()

    def test_get_returns_stash_with_id_when_exists(self):
        db, service, campaign_id = self._make_service()
        try:
            # Create first
            service.create_stash(
                campaign_id,
                PartyStashCreate(
                    wealth=WealthDto(
                        coins=[CoinEntryDto(value=10, type="gp")],
                        total_value={"value": 0.0, "type": "gp"},
                    ),
                    loot=[],
                ),
            )

            # GET should now return with id
            stash = service.get_stash(campaign_id)
            self.assertIsNotNone(stash.id)
            self.assertEqual(len(stash.wealth.coins), 1)
        finally:
            db.close()

    # ── GET 404 ─────────────────────────────────────────────────────

    def test_get_stash_nonexistent_campaign_raises_404(self):
        db, service, _ = self._make_service()
        try:
            from fastapi import HTTPException

            with self.assertRaises(HTTPException) as ctx:
                service.get_stash(99999)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            db.close()

    # ── CREATE (POST) ───────────────────────────────────────────────

    def test_create_stash_returns_id(self):
        db, service, campaign_id = self._make_service()
        try:
            result = service.create_stash(
                campaign_id,
                PartyStashCreate(
                    wealth=WealthDto(
                        coins=[CoinEntryDto(value=50, type="gp")],
                        total_value={"value": 0.0, "type": "gp"},
                    ),
                    loot=[
                        LootItemUpdate(
                            name="Gem",
                            desc="A ruby",
                            value=CoinEntryDto(value=100, type="gp"),
                        ),
                    ],
                ),
            )

            self.assertIsNotNone(result.id)
            self.assertEqual(len(result.wealth.coins), 1)
            self.assertEqual(result.wealth.total_value.value, 50.0)
            self.assertEqual(len(result.loot), 1)
            self.assertEqual(result.loot[0].name, "Gem")
        finally:
            db.close()

    def test_create_stash_twice_is_idempotent(self):
        db, service, campaign_id = self._make_service()
        try:
            payload = PartyStashCreate(
                wealth=WealthDto(
                    coins=[CoinEntryDto(value=10, type="gp")],
                    total_value={"value": 0.0, "type": "gp"},
                ),
                loot=[],
            )
            first = service.create_stash(campaign_id, payload)

            payload2 = PartyStashCreate(
                wealth=WealthDto(
                    coins=[CoinEntryDto(value=20, type="pp")],
                    total_value={"value": 0.0, "type": "gp"},
                ),
                loot=[],
            )
            second = service.create_stash(campaign_id, payload2)

            # Same stash id, new data
            self.assertEqual(first.id, second.id)
            self.assertEqual(len(second.wealth.coins), 1)
            self.assertEqual(second.wealth.total_value.value, 200.0)
        finally:
            db.close()

    # ── UPDATE (PUT) ────────────────────────────────────────────────

    def test_update_stash_on_existing(self):
        db, service, campaign_id = self._make_service()
        try:
            # Create first
            service.create_stash(
                campaign_id,
                PartyStashCreate(
                    wealth=WealthDto(
                        coins=[CoinEntryDto(value=100, type="cp")],
                        total_value={"value": 0.0, "type": "gp"},
                    ),
                    loot=[],
                ),
            )

            # Now update
            updated = service.update_stash(
                campaign_id,
                PartyStashUpdate(
                    wealth=WealthDto(
                        coins=[
                            CoinEntryDto(value=100, type="cp"),
                            CoinEntryDto(value=10, type="gp"),
                        ],
                        total_value={"value": 0.0, "type": "gp"},
                    ),
                    loot=[
                        LootItemUpdate(
                            name="Elven Ring",
                            desc="Shiny ring with engraving",
                            value=CoinEntryDto(value=150, type="gp"),
                        ),
                        LootItemUpdate(
                            name="Ork Shield",
                            desc="Smelly battle shield",
                            value=CoinEntryDto(value=100, type="sp"),
                        ),
                    ],
                ),
            )

            # coins: 100 cp (1 gp) + 10 gp = 11 gp
            self.assertEqual(len(updated.wealth.coins), 2)
            self.assertEqual(updated.wealth.total_value.value, 11.0)
            self.assertEqual(len(updated.loot), 2)
            self.assertEqual(updated.loot[0].name, "Elven Ring")
            self.assertEqual(updated.loot[0].value.value, 150)
            self.assertEqual(updated.loot[0].value.type, "gp")
        finally:
            db.close()

    def test_update_stash_nonexistent_raises_404(self):
        db, service, campaign_id = self._make_service()
        try:
            from fastapi import HTTPException

            payload = PartyStashUpdate(
                wealth=WealthDto(
                    coins=[],
                    total_value={"value": 0.0, "type": "gp"},
                ),
                loot=[],
            )

            with self.assertRaises(HTTPException) as ctx:
                service.update_stash(campaign_id, payload)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            db.close()

    # ── ADD LOOT ITEM ───────────────────────────────────────────────

    def test_add_loot_item_auto_creates_stash(self):
        db, service, campaign_id = self._make_service()
        try:
            # No stash exists yet
            stash_before = service.get_stash(campaign_id)
            self.assertIsNone(stash_before.id)

            # Adding loot creates the stash
            payload = LootItemUpdate(
                name="Sunblade",
                desc="Glows with solar energy",
                value=CoinEntryDto(value=5000, type="gp"),
            )
            added = service.add_loot_item(campaign_id, payload)
            self.assertIsNotNone(added.id)
            self.assertEqual(added.name, "Sunblade")
            self.assertEqual(added.value.value, 5000)

            # Stash now exists with an id
            stash_after = service.get_stash(campaign_id)
            self.assertIsNotNone(stash_after.id)
            self.assertEqual(len(stash_after.loot), 1)
        finally:
            db.close()

    def test_add_and_delete_loot_item(self):
        db, service, campaign_id = self._make_service()
        try:
            # Create stash, then add loot
            service.create_stash(
                campaign_id,
                PartyStashCreate(
                    wealth=WealthDto(
                        coins=[],
                        total_value={"value": 0.0, "type": "gp"},
                    ),
                    loot=[],
                ),
            )

            payload = LootItemUpdate(
                name="Sunblade",
                desc="Glows with solar energy",
                value=CoinEntryDto(value=5000, type="gp"),
            )
            added = service.add_loot_item(campaign_id, payload)
            self.assertIsNotNone(added.id)
            self.assertEqual(added.name, "Sunblade")

            # Verify it's in the stash
            stash = service.get_stash(campaign_id)
            self.assertEqual(len(stash.loot), 1)
            self.assertEqual(stash.loot[0].id, added.id)

            # Delete the item
            result = service.delete_loot_item(campaign_id, added.id)
            self.assertIsNone(result)

            # Verify stash is empty
            stash2 = service.get_stash(campaign_id)
            self.assertEqual(len(stash2.loot), 0)
        finally:
            db.close()

    # ── DELETE LOOT 404s ────────────────────────────────────────────

    def test_delete_loot_item_nonexistent_stash_raises_404(self):
        db, service, campaign_id = self._make_service()
        try:
            from fastapi import HTTPException

            with self.assertRaises(HTTPException) as ctx:
                service.delete_loot_item(campaign_id, 999)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            db.close()

    def test_delete_loot_item_nonexistent_item_raises_404(self):
        db, service, campaign_id = self._make_service()
        try:
            from fastapi import HTTPException

            service.create_stash(
                campaign_id,
                PartyStashCreate(
                    wealth=WealthDto(
                        coins=[],
                        total_value={"value": 0.0, "type": "gp"},
                    ),
                    loot=[],
                ),
            )

            with self.assertRaises(HTTPException) as ctx:
                service.delete_loot_item(campaign_id, 999)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
