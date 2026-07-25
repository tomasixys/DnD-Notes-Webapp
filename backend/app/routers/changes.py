from fastapi import APIRouter, Depends, Query

from app.authorization.context import CampaignContext
from app.authorization.dependencies import get_shared_read_context
from app.models.api import CampaignChangesRead
from app.services.campaign_changes import CampaignChangeService


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/changes",
    tags=["changes"],
)


@router.get("")
def get_campaign_changes(
    after: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=250),
    context: CampaignContext = Depends(get_shared_read_context),
) -> CampaignChangesRead:
    return CampaignChangeService(context).list_changes(
        after,
        limit=limit,
    )
