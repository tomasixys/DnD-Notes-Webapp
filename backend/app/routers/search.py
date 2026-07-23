from fastapi import APIRouter, Depends

from app.dependencies.campaigns import get_campaign_context
from app.models.api import SearchQueryDto, SearchResponseDto
from app.services.campaign_context import CampaignContext
from app.services.search import SearchService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/search",
    tags=["search"],
)


@router.post("")
def search_campaign(
    campaign_id: int,
    queryDto: SearchQueryDto,
    context: CampaignContext = Depends(get_campaign_context),
) -> SearchResponseDto:
    return SearchService(context).search(queryDto)
