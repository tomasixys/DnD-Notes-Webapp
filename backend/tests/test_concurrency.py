import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignRole, ResourceVisibility
from app.authorization.models import CampaignMembership
from app.models.api import CharacterCreate, CharacterNoteData, PersonData
from app.models.database import Campaign, Person
from app.services.campaign_changes import CampaignChangeService
from app.services.character_notes import CharacterNoteService
from app.services.characters import CharacterService
from app.services.people import PersonService
from tests.authorization_helpers import campaign_context, create_user


class OptimisticConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "test.db"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_stale_update_is_rejected_without_overwriting_newer_data(self):
        with Session(self.engine) as setup:
            campaign = Campaign(name="Concurrency")
            setup.add(campaign)
            setup.flush()
            owner = campaign_context(setup, campaign)
            created = PersonService(owner).create(
                PersonData(name="Nalia", role="Wizard")
            )
            campaign_id = campaign.id
            user_id = owner.user.id
            person_id = created.id

        with Session(self.engine) as first, Session(self.engine) as second:
            first_context = CampaignContext.resolve(
                first,
                campaign_id,
                first.get(type(owner.user), user_id),
            )
            second_context = CampaignContext.resolve(
                second,
                campaign_id,
                second.get(type(owner.user), user_id),
            )
            first_service = PersonService(first_context)
            second_service = PersonService(second_context)
            self.assertEqual(1, first_service.get(person_id).revision)
            self.assertEqual(1, second_service.get(person_id).revision)

            saved = first_service.update(
                person_id,
                PersonData(name="Nalia", role="Archmage"),
                expected_revision=1,
            )
            self.assertEqual(2, saved.revision)

            with self.assertRaises(HTTPException) as stale:
                second_service.update(
                    person_id,
                    PersonData(name="Nalia", role="Apprentice"),
                    expected_revision=1,
                )

            self.assertEqual(409, stale.exception.status_code)
            self.assertEqual(
                {
                    "code": "revision_conflict",
                    "resource_type": "person",
                    "resource_id": person_id,
                    "expected_revision": 1,
                    "current_revision": 2,
                    "message": (
                        "This resource changed after it was loaded. "
                        "Reload the current version before saving again."
                    ),
                },
                stale.exception.detail,
            )
            second.rollback()

        with Session(self.engine) as verify:
            person = verify.get(Person, person_id)
            self.assertEqual("Archmage", person.role)
            self.assertEqual(2, person.revision)

    def test_stale_delete_does_not_remove_newer_data(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Concurrency")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            people = PersonService(owner)
            person = people.create(PersonData(name="Imoen"))
            people.update(
                person.id,
                PersonData(name="Imoen", role="Mage"),
                expected_revision=person.revision,
            )

            with self.assertRaises(HTTPException) as stale:
                people.delete(person.id, expected_revision=person.revision)

            self.assertEqual(409, stale.exception.status_code)
            db.rollback()
            preserved = db.get(Person, person.id)
            self.assertEqual("Mage", preserved.role)
            self.assertEqual(2, preserved.revision)

    def test_membership_removal_blocks_a_later_stale_edit_request(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Revoked access")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            person = PersonService(owner).create(PersonData(name="Imoen"))
            member_user = create_user(db)
            member = CampaignMembership(
                campaign_id=campaign.id,
                user_id=member_user.id,
                role=CampaignRole.MEMBER,
            )
            db.add(member)
            db.commit()

            loaded_context = CampaignContext.resolve(
                db,
                campaign.id,
                member_user,
            )
            loaded_revision = PersonService(loaded_context).get(
                person.id
            ).revision
            self.assertEqual(1, loaded_revision)

            db.delete(member)
            db.commit()

            with self.assertRaises(HTTPException) as removed:
                CampaignContext.resolve(db, campaign.id, member_user)
            self.assertEqual(404, removed.exception.status_code)


class CampaignChangeCursorTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_private_changes_use_independent_recipient_sequences(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Private changes")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            character = CharacterService(owner).create(
                CharacterCreate(person=PersonData(name="Nalia"))
            )
            owner.membership.assigned_character_person_id = None
            owner.membership.active_character_person_id = None
            member_user = create_user(db)
            viewer_user = create_user(db)
            member_membership = CampaignMembership(
                campaign_id=campaign.id,
                user_id=member_user.id,
                role=CampaignRole.MEMBER,
                assigned_character_person_id=character.person.id,
                active_character_person_id=character.person.id,
            )
            viewer_membership = CampaignMembership(
                campaign_id=campaign.id,
                user_id=viewer_user.id,
                role=CampaignRole.VIEWER,
            )
            db.add(member_membership)
            db.add(viewer_membership)
            db.commit()

            member = CampaignContext(
                db,
                campaign,
                member_user,
                member_membership,
            )
            viewer = CampaignContext(
                db,
                campaign,
                viewer_user,
                viewer_membership,
            )
            owner_cursor = CampaignChangeService(owner).list_changes(None).cursor
            member_cursor = CampaignChangeService(member).list_changes(None).cursor
            viewer_cursor = CampaignChangeService(viewer).list_changes(None).cursor

            CharacterNoteService(member).create(
                character.person.id,
                CharacterNoteData(
                    title="Private plan",
                    visibility=ResourceVisibility.PRIVATE,
                ),
            )
            PersonService(owner).create(PersonData(name="Jaheira"))

            owner_changes = CampaignChangeService(owner).list_changes(
                owner_cursor
            )
            member_changes = CampaignChangeService(member).list_changes(
                member_cursor
            )
            viewer_changes = CampaignChangeService(viewer).list_changes(
                viewer_cursor
            )

            self.assertEqual(
                [("person", "created")],
                [
                    (change.resource_type, change.action)
                    for change in owner_changes.changes
                ],
            )
            self.assertEqual(
                [
                    ("character_note", "created"),
                    ("person", "created"),
                ],
                [
                    (change.resource_type, change.action)
                    for change in member_changes.changes
                ],
            )
            self.assertEqual(
                [("person", "created")],
                [
                    (change.resource_type, change.action)
                    for change in viewer_changes.changes
                ],
            )
            self.assertEqual(
                member_cursor + 2,
                member_changes.cursor,
            )
            self.assertEqual(
                owner_cursor + 1,
                owner_changes.cursor,
            )
            self.assertEqual(
                viewer_cursor + 1,
                viewer_changes.cursor,
            )

    def test_change_poll_skips_saves_from_same_client_instance(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Multiple tabs")
            db.add(campaign)
            db.flush()
            owner = campaign_context(db, campaign)
            owner.client_instance_id = "tab-a"
            changes = CampaignChangeService(owner)
            baseline = changes.list_changes(None).cursor

            PersonService(owner).create(PersonData(name="Jaheira"))

            same_tab = changes.list_changes(baseline)
            self.assertEqual([], same_tab.changes)
            self.assertEqual(baseline + 1, same_tab.cursor)

            owner.client_instance_id = "tab-b"
            other_tab = changes.list_changes(baseline)
            self.assertEqual(
                [("person", "created")],
                [
                    (change.resource_type, change.action)
                    for change in other_tab.changes
                ],
            )
            self.assertEqual(baseline + 1, other_tab.cursor)


if __name__ == "__main__":
    unittest.main()
