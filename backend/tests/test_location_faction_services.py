import unittest

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.api import FactionData, LocationData
from app.models.database import (
    Campaign,
    Faction,
    Location,
    TagAssignment,
)
from app.services.campaign_context import CampaignContext
from app.services.factions import FactionService
from app.services.locations import LocationService


class LocationAndFactionServiceTests(unittest.TestCase):
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
    def _create_context(db: Session) -> CampaignContext:
        campaign = Campaign(name="Test")
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return CampaignContext(db, campaign)

    def test_staged_resources_and_relationships_share_outer_transaction(self):
        with Session(self.engine) as db:
            context = self._create_context(db)
            locations = LocationService(context)
            factions = FactionService(context)

            city = locations.stage_create(
                LocationData(name="Gernanti", tags=["capital"])
            )
            academy = locations.stage_create(
                LocationData(
                    name="Academy",
                    parent_location="Gernanti",
                )
            )
            faction = factions.stage_create(
                FactionData(
                    name="Dragon Order",
                    location="Academy",
                )
            )
            city_id = city.id
            academy_id = academy.id
            faction_id = faction.id

            self.assertEqual(
                "Gernanti",
                locations.to_read(academy).parent_location.label,
            )
            self.assertEqual(
                "Academy",
                factions.to_read(faction).location.label,
            )
            self.assertGreater(
                len(db.exec(select(TagAssignment)).all()),
                0,
            )

            db.rollback()

            self.assertIsNone(db.get(Location, city_id))
            self.assertIsNone(db.get(Location, academy_id))
            self.assertIsNone(db.get(Faction, faction_id))
            self.assertEqual([], db.exec(select(TagAssignment)).all())

    def test_standalone_services_propagate_renames_and_commit_deletes(self):
        with Session(self.engine) as db:
            context = self._create_context(db)
            locations = LocationService(context)
            factions = FactionService(context)

            locations.create(LocationData(name="Gernanti"))
            academy = locations.create(
                LocationData(
                    name="Academy",
                    parent_location="Gernanti",
                )
            )
            faction = factions.create(
                FactionData(
                    name="Dragon Order",
                    location="Academy",
                )
            )

            locations.update(
                academy.id,
                LocationData(
                    name="Grand Academy",
                    parent_location="Gernanti",
                ),
            )
            refreshed_faction = factions.to_read(
                factions.get(faction.id)
            )
            self.assertEqual(
                "Grand Academy",
                refreshed_faction.location.label,
            )

            faction_id = faction.id
            academy_id = academy.id
            factions.delete(faction_id)
            locations.delete(academy_id)

            self.assertIsNone(db.get(Faction, faction_id))
            self.assertIsNone(db.get(Location, academy_id))

    def test_self_parent_validation_rolls_back_location_creation(self):
        with Session(self.engine) as db:
            context = self._create_context(db)

            with self.assertRaises(HTTPException) as error:
                LocationService(context).create(
                    LocationData(
                        name="Loop",
                        parent_location="Loop",
                    )
                )

            self.assertEqual(400, error.exception.status_code)
            self.assertEqual([], db.exec(select(Location)).all())

    def test_backup_lists_are_campaign_scoped_and_name_ordered(self):
        with Session(self.engine) as db:
            context = self._create_context(db)
            locations = LocationService(context)
            factions = FactionService(context)

            locations.create(LocationData(name="zeta"))
            locations.create(LocationData(name="Alpha"))
            factions.create(FactionData(name="wolves"))
            factions.create(FactionData(name="Bards"))

            other_campaign = Campaign(name="Other")
            db.add(other_campaign)
            db.commit()
            db.refresh(other_campaign)
            other_context = CampaignContext(db, other_campaign)
            LocationService(other_context).create(
                LocationData(name="Hidden")
            )
            FactionService(other_context).create(
                FactionData(name="Hidden")
            )

            self.assertEqual(
                ["Alpha", "zeta"],
                [
                    entry.name
                    for entry in locations.list_backup_entries()
                ],
            )
            self.assertEqual(
                ["Bards", "wolves"],
                [
                    entry.name
                    for entry in factions.list_backup_entries()
                ],
            )


if __name__ == "__main__":
    unittest.main()
