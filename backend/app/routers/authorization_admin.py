from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.auth.dependencies import require_current_user
from app.auth.models import User
from app.authorization.administration import (
    CampaignAuthorizationAdminService,
)
from app.authorization.schemas import (
    AdminCampaignRead,
    CampaignRecoveryRequest,
)
from app.backup_downloads import (
    BINARY_DOWNLOAD_RESPONSE,
    backup_file_response,
)
from app.database import get_session
from app.services.campaign_backups import CampaignBackupService


router = APIRouter(
    prefix="/api/admin/campaigns",
    tags=["campaign-authorization-admin"],
)


def _to_read(context) -> AdminCampaignRead:
    return AdminCampaignRead(
        id=context.campaign_id,
        name=context.campaign.name,
        orphaned=context.campaign.orphaned,
    )


@router.get("/{campaign_id}")
def inspect_campaign(
    campaign_id: int,
    reason: str = Query(min_length=1),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> AdminCampaignRead:
    return _to_read(
        CampaignAuthorizationAdminService(db, user).inspect(
            campaign_id,
            reason,
        )
    )


@router.post("/{campaign_id}/recover")
def recover_campaign(
    campaign_id: int,
    payload: CampaignRecoveryRequest,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> AdminCampaignRead:
    return _to_read(
        CampaignAuthorizationAdminService(db, user).recover(
            campaign_id,
            payload.owner_user_id,
            payload.reason,
        )
    )


@router.get(
    "/{campaign_id}/backup/export",
    response_class=FileResponse,
    responses=BINARY_DOWNLOAD_RESPONSE,
)
def export_campaign(
    campaign_id: int,
    reason: str = Query(min_length=1),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> FileResponse:
    context = CampaignAuthorizationAdminService(db, user).inspect(
        campaign_id,
        reason,
    )
    return backup_file_response(
        CampaignBackupService(db, user).export(context)
    )
