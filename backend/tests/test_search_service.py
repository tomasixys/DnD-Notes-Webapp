import unittest

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.api import FactionData, PersonData, SearchQueryDto
from app.models.database import Campaign
from app.models.enums import ResourceType
from app.services.campaign_context import CampaignContext
from app.services.factions import FactionService
from app.services.people import PersonService
from app.services.search import SearchService


class SearchServiceTests(unittest.TestCase):
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
    def _create_context(
        db: Session,
        name: str,
    ) -> CampaignContext:
        campaign = Campaign(name=name)
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return CampaignContext(db, campaign)

    def test_search_is_scoped_filtered_and_relevance_ordered(self):
        with Session(self.engine) as db:
            context = self._create_context(db, "Current")
            people = PersonService(context)
            people.create(PersonData(name="Nalia"))
            people.create(PersonData(name="Nalia Scout"))
            FactionService(context).create(
                FactionData(name="Nalia Order")
            )

            other_context = self._create_context(db, "Other")
            PersonService(other_context).create(
                PersonData(name="Nalia Elsewhere")
            )

            response = SearchService(context).search(
                SearchQueryDto(
                    query="Nalia",
                    resource_types=[ResourceType.PERSON.value],
                )
            )

            self.assertEqual(
                [ResourceType.PERSON],
                response.searched_resource_types,
            )
            self.assertEqual(
                ["Nalia", "Nalia Scout"],
                [result.title for result in response.results],
            )
            self.assertEqual(
                [context.campaign_id, context.campaign_id],
                [result.campaign_id for result in response.results],
            )
            self.assertGreater(
                response.results[0].relevance,
                response.results[1].relevance,
            )

    def test_search_validates_query_and_resource_types(self):
        with Session(self.engine) as db:
            context = self._create_context(db, "Current")
            search = SearchService(context)

            with self.assertRaises(HTTPException) as blank_error:
                search.search(SearchQueryDto(query="  "))
            self.assertEqual(422, blank_error.exception.status_code)

            with self.assertRaises(HTTPException) as type_error:
                search.search(
                    SearchQueryDto(
                        query="Nalia",
                        resource_types=["unknown"],
                    )
                )
            self.assertEqual(400, type_error.exception.status_code)


if __name__ == "__main__":
    unittest.main()
