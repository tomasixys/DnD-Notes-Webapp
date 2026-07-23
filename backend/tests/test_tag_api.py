import unittest

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.database import (
    Campaign,
    Tag,
    TagAssignment,
)

from app.models.api import (
    FactionData,
    LocationData,
    PersonData,
    SearchQueryDto,
)

from app.models.enums import RelationshipType, ResourceType
from app.routers.factions import create_faction, get_factions_for_campaign
from app.routers.locations import (
    create_location,
    get_locations_for_campaign,
    update_location,
)
from app.routers.people import create_person, get_people_for_campaign, update_person
from app.routers.search import search_campaign
from app.services.campaign_context import CampaignContext


class TagApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def test_resource_endpoints_return_structured_tags_and_search_tags(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            context = CampaignContext(db, campaign)

            location = create_location(
                campaign.id,
                LocationData(name="Skummende Seidel", type="Tavern"),
                db,
            )
            person = create_person(
                campaign.id,
                PersonData(
                    name="Nalia",
                    tags=["location:Skummende Seidel", "Neutral"],
                ),
                context,
            )

            self.assertEqual(
                [tag.value for tag in person.tags],
                ["Neutral", "location:Skummende Seidel"],
            )
            self.assertEqual(
                [tag.label for tag in person.tags],
                ["Neutral", "Skummende Seidel"],
            )
            self.assertEqual(
                get_people_for_campaign(campaign.id, context)[0].tags,
                person.tags,
            )
            self.assertEqual(
                person.tags[1].reference_type,
                ResourceType.LOCATION,
            )
            self.assertEqual(person.tags[1].reference_id, location.id)
            self.assertEqual(
                person.tags[1].relationship_type,
                RelationshipType.ASSOCIATED_WITH,
            )

            tag = db.exec(
                select(Tag).where(
                    Tag.reference_type == ResourceType.LOCATION.value
                )
            ).one()
            self.assertEqual(tag.reference_id, location.id)

            search_response = search_campaign(
                campaign.id,
                SearchQueryDto(
                    query="Skummende Seidel",
                    resource_types=[ResourceType.PERSON.value],
                ),
                db,
            )
            self.assertEqual(search_response.total_count, 1)
            self.assertEqual(search_response.results[0].title, "Nalia")
            self.assertIn("tags", search_response.results[0].matched_fields)

    def test_renaming_a_target_updates_and_merges_reference_tags(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            context = CampaignContext(db, campaign)

            location = create_location(
                campaign.id,
                LocationData(name="Old Harbor"),
                db,
            )
            create_person(
                campaign.id,
                PersonData(name="Nalia", tags=["location:Old Harbor"]),
                context,
            )
            create_person(
                campaign.id,
                PersonData(name="Sodalan", tags=["location:New Harbor"]),
                context,
            )

            update_location(
                campaign.id,
                location.id,
                LocationData(name="New Harbor"),
                db,
            )

            people = get_people_for_campaign(campaign.id, context)
            for person in people:
                self.assertEqual(len(person.tags), 1)
                self.assertEqual(person.tags[0].value, "location:New Harbor")
                self.assertEqual(person.tags[0].label, "New Harbor")
                self.assertEqual(person.tags[0].reference_id, location.id)

            reference_tags = db.exec(
                select(Tag).where(Tag.reference_type == "location")
            ).all()
            assignments = db.exec(select(TagAssignment)).all()
            self.assertEqual(len(reference_tags), 1)
            self.assertEqual(
                reference_tags[0].key,
                f"reference:location:{location.id}",
            )
            self.assertEqual(len(assignments), 2)

    def test_relationship_fields_use_tags_and_populate_inverse_lists(self):
        with Session(self.engine) as db:
            campaign = Campaign(name="Test")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            context = CampaignContext(db, campaign)

            city = create_location(
                campaign.id,
                LocationData(name="Gernanti"),
                db,
            )
            academy = create_location(
                campaign.id,
                LocationData(name="Academy", parent_location="Gernanti"),
                db,
            )
            faction = create_faction(
                campaign.id,
                FactionData(name="Dragon Order", location="Academy"),
                db,
            )
            person = create_person(
                campaign.id,
                PersonData(
                    name="Nalia",
                    faction="Dragon Order",
                    location="Academy",
                    tags=["location:Academy", "ally"],
                ),
                context,
            )

            self.assertEqual(person.faction.reference_id, faction.id)
            self.assertEqual(
                person.faction.relationship_type,
                RelationshipType.MEMBER_OF,
            )
            self.assertEqual(person.location.reference_id, academy.id)
            self.assertEqual(
                person.location.relationship_type,
                RelationshipType.LOCATED_IN,
            )
            self.assertEqual(academy.parent_location.reference_id, city.id)
            self.assertEqual(
                academy.parent_location.relationship_type,
                RelationshipType.PART_OF,
            )
            self.assertEqual(faction.location.reference_id, academy.id)
            self.assertEqual(
                faction.location.relationship_type,
                RelationshipType.BASED_IN,
            )
            self.assertEqual(
                [tag.value for tag in person.tags],
                ["ally", "location:Academy"],
            )

            faction_read = get_factions_for_campaign(campaign.id, db)[0]
            academy_read = next(
                location
                for location in get_locations_for_campaign(campaign.id, db)
                if location.id == academy.id
            )
            self.assertEqual([member.label for member in faction_read.members], ["Nalia"])
            self.assertEqual([resident.label for resident in academy_read.people], ["Nalia"])

            updated = update_person(
                campaign.id,
                person.id,
                PersonData(
                    name="Nalia",
                    faction="Dragon Order",
                    location="Academy",
                    tags=["trusted"],
                ),
                context,
            )
            self.assertEqual(updated.faction.reference_id, faction.id)
            self.assertEqual(updated.location.reference_id, academy.id)
            self.assertEqual([tag.value for tag in updated.tags], ["trusted"])

            assignments = db.exec(
                select(TagAssignment)
                .where(TagAssignment.owner_type == ResourceType.PERSON.value)
                .where(TagAssignment.owner_id == person.id)
            ).all()
            self.assertEqual(
                {assignment.relationship_type for assignment in assignments},
                {
                    RelationshipType.ASSOCIATED_WITH.value,
                    RelationshipType.LOCATED_IN.value,
                    RelationshipType.MEMBER_OF.value,
                },
            )


if __name__ == "__main__":
    unittest.main()
