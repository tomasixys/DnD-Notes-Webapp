import unittest

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.api import PersonData
from app.models.database import Campaign, Person
from app.services.people import PersonService


class PersonServiceTests(unittest.TestCase):
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

    def test_add_flushes_without_committing_for_composed_operations(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            person = PersonService(db).add(
                campaign,
                PersonData(
                    name="  Nalia  ",
                    role="  Wizard  ",
                    tags=["ally"],
                ),
            )
            person_id = person.id

            self.assertIsNotNone(person_id)
            self.assertEqual("Nalia", person.name)
            self.assertEqual("Wizard", person.role)

            db.rollback()
            self.assertIsNone(db.get(Person, person_id))

    def test_create_update_and_delete_own_their_transactions(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            people = PersonService(db)

            created = people.create(
                campaign,
                PersonData(name="Nalia", role="Wizard"),
            )
            person_id = created.id
            self.assertIsNotNone(db.get(Person, person_id))

            updated = people.update(
                campaign,
                person_id,
                PersonData(name="Nalia", role="Archmage"),
            )
            self.assertEqual("Archmage", updated.role)

            people.delete(campaign, person_id)
            self.assertIsNone(db.get(Person, person_id))

    def test_apply_changes_resolves_by_id_without_committing(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            people = PersonService(db)
            person_id = people.create(
                campaign,
                PersonData(name="Nalia", role="Wizard"),
            ).id

            person = people.apply_changes(
                campaign,
                person_id,
                PersonData(name="Nalia", role="Archmage"),
            )

            self.assertEqual("Archmage", person.role)
            db.rollback()
            self.assertEqual("Wizard", db.get(Person, person_id).role)


if __name__ == "__main__":
    unittest.main()
