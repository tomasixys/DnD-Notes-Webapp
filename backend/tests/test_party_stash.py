import unittest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.database import Campaign
from app.models.api import (
    PartyStashUpdate,
    WealthDto,
    CoinEntryDto,
    LootItemUpdate,
)
from app.routers.party.stash import get_party_stash, update_party_stash, add_loot_item, delete_loot_item


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

    def test_creates_default_stash_when_first_get_requested(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Fellowship")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            stash = get_party_stash(campaign.id, db)

            # Check defaults
            self.assertEqual(len(stash["wealth"]["coins"]), 0)
            self.assertEqual(stash["wealth"]["total_value"]["value"], 0.0)
            self.assertEqual(stash["wealth"]["total_value"]["type"], "gp")
            self.assertEqual(len(stash["loot"]), 0)

    def test_update_and_retrieve_party_stash(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Fellowship")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            payload = PartyStashUpdate(
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
            )

            updated = update_party_stash(campaign.id, payload, db)

            # Check that it returns updated data
            self.assertEqual(len(updated["wealth"]["coins"]), 2)
            # coins: 100 cp (1 gp) + 10 gp = 11 gp
            self.assertEqual(updated["wealth"]["total_value"]["value"], 11.0)

            self.assertEqual(len(updated["loot"]), 2)
            self.assertEqual(updated["loot"][0]["name"], "Elven Ring")
            self.assertEqual(updated["loot"][0]["value"].value, 150)
            self.assertEqual(updated["loot"][0]["value"].type, "gp")
            self.assertEqual(updated["loot"][1]["value"].value, 100)
            self.assertEqual(updated["loot"][1]["value"].type, "sp")

            # Retrieve again via get_party_stash and verify
            retrieved = get_party_stash(campaign.id, db)
            self.assertEqual(len(retrieved["wealth"]["coins"]), 2)
            self.assertEqual(retrieved["wealth"]["total_value"]["value"], 11.0)
            self.assertEqual(len(retrieved["loot"]), 2)

            # Second update with different payload to trigger deletion/cleansing logic
            payload2 = PartyStashUpdate(
                wealth=WealthDto(
                    coins=[
                        CoinEntryDto(value=20, type="pp"),
                    ],
                    total_value={"value": 0.0, "type": "gp"},
                ),
                loot=[
                    LootItemUpdate(
                        name="Elven Ring",
                        desc="Shiny ring with engraving",
                        value=CoinEntryDto(value=150, type="gp"),
                    ),
                ],
            )
            updated2 = update_party_stash(campaign.id, payload2, db)
            self.assertEqual(len(updated2["wealth"]["coins"]), 1)
            self.assertEqual(updated2["wealth"]["total_value"]["value"], 200.0)
            self.assertEqual(len(updated2["loot"]), 1)

    def test_add_and_delete_loot_item_individually(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Fellowship")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            # Add loot item
            payload = LootItemUpdate(
                name="Sunblade",
                desc="Glows with solar energy",
                value=CoinEntryDto(value=5000, type="gp"),
            )
            added = add_loot_item(campaign.id, payload, db)
            self.assertIsNotNone(added["id"])
            self.assertEqual(added["name"], "Sunblade")
            self.assertEqual(added["value"].value, 5000)
            self.assertEqual(added["value"].type, "gp")

            # Check that it's in the stash
            stash = get_party_stash(campaign.id, db)
            self.assertEqual(len(stash["loot"]), 1)
            self.assertEqual(stash["loot"][0]["id"], added["id"])

            # Delete the item
            delete_result = delete_loot_item(campaign.id, added["id"], db)
            self.assertTrue(delete_result["success"])

            # Check that the stash is empty again
            stash2 = get_party_stash(campaign.id, db)
            self.assertEqual(len(stash2["loot"]), 0)


if __name__ == "__main__":
    unittest.main()
