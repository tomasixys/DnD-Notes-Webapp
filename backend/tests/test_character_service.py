import unittest
from unittest.mock import Mock, call, patch

from fastapi import UploadFile
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

            deleted = characters.delete(person_id)
            self.assertEqual(person_id, deleted.deleted_id)
            self.assertIsNone(deleted.active_character)
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

    def test_delete_returns_the_remaining_active_character(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            characters = CharacterService(CampaignContext(db, campaign))

            active = characters.create(
                CharacterCreate(person=PersonData(name="Nalia")),
            )
            inactive = characters.create(
                CharacterCreate(
                    person=PersonData(name="Sable"),
                    make_active=False,
                ),
            )
            inactive_id = inactive.person.id

            deleted = characters.delete(inactive_id)

            self.assertEqual(inactive_id, deleted.deleted_id)
            self.assertEqual(
                active.person.id,
                deleted.active_character.person.id,
            )
            self.assertIsNone(db.get(CharacterProfile, inactive_id))

    def test_portrait_replacement_and_removal_update_storage_after_commit(
        self,
    ):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            characters = CharacterService(CampaignContext(db, campaign))
            created = characters.create(
                CharacterCreate(person=PersonData(name="Nalia")),
            )
            person_id = created.person.id
            old_portrait_path = (
                f"campaigns/{campaign.id}/old.png"
            )
            new_portrait_path = (
                f"campaigns/{campaign.id}/new.png"
            )
            profile = db.get(CharacterProfile, person_id)
            profile.image_path = old_portrait_path
            db.add(profile)
            db.commit()

            image = Mock(spec=UploadFile)
            with (
                patch(
                    "app.services.characters."
                    "save_image_from_uploadfile",
                    return_value=new_portrait_path,
                ) as save_image,
                patch(
                    "app.services.characters.delete_uploaded_file"
                ) as delete_image,
            ):
                replaced = characters.replace_portrait(person_id, image)

                self.assertEqual(
                    f"uploads/{new_portrait_path}",
                    replaced.image_url,
                )
                self.assertEqual(
                    new_portrait_path,
                    db.get(CharacterProfile, person_id).image_path,
                )
                save_image.assert_called_once_with(campaign.id, image)
                delete_image.assert_called_once_with(old_portrait_path)

                removed = characters.remove_portrait(person_id)

                self.assertEqual("", removed.image_url)
                self.assertEqual(
                    "",
                    db.get(CharacterProfile, person_id).image_path,
                )
                self.assertEqual(
                    [
                        call(old_portrait_path),
                        call(new_portrait_path),
                    ],
                    delete_image.call_args_list,
                )

    def test_portrait_replacement_rolls_back_and_removes_new_file(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            characters = CharacterService(CampaignContext(db, campaign))
            created = characters.create(
                CharacterCreate(person=PersonData(name="Nalia")),
            )
            person_id = created.person.id
            old_portrait_path = (
                f"campaigns/{campaign.id}/old.png"
            )
            new_portrait_path = (
                f"campaigns/{campaign.id}/new.png"
            )
            profile = db.get(CharacterProfile, person_id)
            profile.image_path = old_portrait_path
            db.add(profile)
            db.commit()

            image = Mock(spec=UploadFile)
            with (
                patch(
                    "app.services.characters."
                    "save_image_from_uploadfile",
                    return_value=new_portrait_path,
                ),
                patch(
                    "app.services.characters.delete_uploaded_file"
                ) as delete_image,
                patch.object(
                    db,
                    "commit",
                    side_effect=RuntimeError("commit failed"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "commit failed",
                ):
                    characters.replace_portrait(person_id, image)

            self.assertEqual(
                old_portrait_path,
                db.get(CharacterProfile, person_id).image_path,
            )
            delete_image.assert_called_once_with(new_portrait_path)


if __name__ == "__main__":
    unittest.main()
