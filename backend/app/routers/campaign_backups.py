from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from app.auth.dependencies import require_current_user
from app.auth.models import User
from app.authorization.context import CampaignContext
from app.authorization.dependencies import get_campaign_export_context
from app.database import get_session
from app.models.api import CampaignBackupExportRead, CampaignRead
from app.services.campaign_backups import CampaignBackupService


router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)


@router.get("/{campaign_id}/backup/export")
def export_campaign_backup(
    context: CampaignContext = Depends(get_campaign_export_context),
) -> CampaignBackupExportRead:
    return CampaignBackupService(
        context.db,
        context.user,
    ).export(context)


@router.post("/backup/import")
async def import_campaign_backup(
    backup: UploadFile = File(...),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> CampaignRead:
    return CampaignBackupService(db, user).import_archive(
        await backup.read()
    )
