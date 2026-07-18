import unittest

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Campaign,
    LocationData,
    PersonData,
    ResourceType,
    SearchQueryDto,
    Tag,
)
from app.routers.locations import create_location
from app.routers.people import create_person, get_people_for_campaign
from app.routers.search import search_campaign


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
                db,
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
                get_people_for_campaign(campaign.id, db)[0].tags,
                person.tags,
            )
            self.assertEqual(
                person.tags[1].reference_type,
                ResourceType.LOCATION,
            )
            self.assertEqual(person.tags[1].reference_id, location.id)

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


if __name__ == "__main__":
    unittest.main()
