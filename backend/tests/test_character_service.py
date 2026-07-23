import unittest

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.api import CharacterCreate, CharacterUpdate, PersonData
from app.models.database import (
    Campaign,
    CharacterProfile,
    InventoryAccess,
    Person,
)
from app.services.campaign_context import CampaignContext
from app.services.characters import CharacterService


class CharacterServiceTests(unittest.TestCase):
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

    def test_stage_create_composes_the_aggregate_without_committing(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            profile = CharacterService(
                CampaignContext(db, campaign)
            ).stage_create(
                CharacterCreate(
                    person=PersonData(name="Nalia"),
                    short_bio="Wizard",
                ),
            )
            person_id = profile.person_id

            self.assertIsNotNone(db.get(Person, person_id))
            self.assertIsNotNone(db.get(CharacterProfile, person_id))
            self.assertEqual(person_id, campaign.active_character_person_id)

            db.rollback()
            self.assertIsNone(db.get(Person, person_id))
            self.assertIsNone(db.get(CharacterProfile, person_id))
            db.refresh(campaign)
            self.assertIsNone(campaign.active_character_person_id)

    def test_standalone_character_operations_own_their_transactions(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            characters = CharacterService(CampaignContext(db, campaign))

            created = characters.create(
                CharacterCreate(
                    person=PersonData(name="Nalia", role="Wizard"),
                    short_bio="Academy exile",
                ),
            )
            person_id = created.person.id

            updated = characters.update(
                person_id,
                CharacterUpdate(
                    person=PersonData(name="Nalia", role="Archmage"),
                    short_bio="Court mage",
                ),
            )
            self.assertEqual("Archmage", updated.person.role)
            self.assertEqual("Court mage", updated.short_bio)

            characters.delete(person_id)
            self.assertIsNone(db.get(CharacterProfile, person_id))
            self.assertIsNotNone(db.get(Person, person_id))

    def test_set_active_pointer_leaves_inventory_grants_unchanged(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            characters = CharacterService(CampaignContext(db, campaign))

            first = characters.create(
                CharacterCreate(person=PersonData(name="Nalia")),
            )
            second = characters.create(
                CharacterCreate(
                    person=PersonData(name="Sable"),
                    make_active=False,
                ),
            )

            characters.set_active_pointer(second.person.id)
            grants = db.exec(select(InventoryAccess)).all()

            self.assertEqual(
                second.person.id,
                campaign.active_character_person_id,
            )
            self.assertEqual(
                [grant.character_person_id for grant in grants],
                [first.person.id],
            )

            db.rollback()


if __name__ == "__main__":
    unittest.main()
