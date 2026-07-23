import unittest

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.database import (
    Campaign,
    Location,
    Person,
    TagAssignment,
)
from app.models.enums import RelationshipType, ResourceType
from app.services.campaign_context import CampaignContext
from app.services.tags import TagService


class TagServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _create_resources(
        db: Session,
        campaign_name: str,
        person_name: str,
    ) -> tuple[CampaignContext, Person, Location]:
        campaign = Campaign(name=campaign_name)
        db.add(campaign)
        db.flush()
        person = Person(
            campaign_id=campaign.id,
            name=person_name,
        )
        location = Location(
            campaign_id=campaign.id,
            name="Academy",
        )
        db.add(person)
        db.add(location)
        db.commit()
        db.refresh(campaign)
        db.refresh(person)
        db.refresh(location)
        return CampaignContext(db, campaign), person, location

    def test_component_scopes_tag_queries_and_relationships(self):
        with Session(self.engine) as db:
            context, person, location = self._create_resources(
                db,
                "Current",
                "Nalia",
            )
            other_context, other_person, _ = self._create_resources(
                db,
                "Other",
                "Sable",
            )
            tags = TagService(context)
            other_tags = TagService(other_context)

            tags.stage_sync_tags(
                ResourceType.PERSON,
                person.id,
                ["ally"],
            )
            tags.stage_sync_relationship(
                ResourceType.PERSON,
                person.id,
                RelationshipType.LOCATED_IN,
                ResourceType.LOCATION,
                location.name,
            )
            other_tags.stage_sync_tags(
                ResourceType.PERSON,
                other_person.id,
                ["ally"],
            )
            db.commit()

            self.assertEqual(
                ["ally"],
                tags.list_values(ResourceType.PERSON, person.id),
            )
            self.assertEqual(
                location.id,
                tags.get_relationship(
                    ResourceType.PERSON,
                    person.id,
                    RelationshipType.LOCATED_IN,
                ).reference_id,
            )
            self.assertEqual(
                [person.id],
                tags.find_matching_owner_ids(
                    ResourceType.PERSON,
                    "%ally%",
                ),
            )
            self.assertEqual(
                ["Nalia"],
                [
                    reference.label
                    for reference in tags.list_referencing_resources(
                        target_type=ResourceType.LOCATION,
                        target_id=location.id,
                        owner_type=ResourceType.PERSON,
                        relationship_type=RelationshipType.LOCATED_IN,
                    )
                ],
            )
            with self.assertRaises(HTTPException) as scope_error:
                tags.list_values(
                    ResourceType.PERSON,
                    other_person.id,
                )
            self.assertEqual(404, scope_error.exception.status_code)

    def test_staged_tag_changes_join_the_outer_transaction(self):
        with Session(self.engine) as db:
            context, person, _ = self._create_resources(
                db,
                "Current",
                "Nalia",
            )
            tags = TagService(context)
            tags.stage_sync_tags(
                ResourceType.PERSON,
                person.id,
                ["temporary"],
            )

            self.assertEqual(
                1,
                len(db.exec(select(TagAssignment)).all()),
            )

            db.rollback()

            self.assertEqual([], db.exec(select(TagAssignment)).all())
            self.assertEqual(
                [],
                tags.list_values(ResourceType.PERSON, person.id),
            )


if __name__ == "__main__":
    unittest.main()
