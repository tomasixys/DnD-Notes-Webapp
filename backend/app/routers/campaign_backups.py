from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.auth.dependencies import require_current_user
from app.auth.models import User
from app.authorization.context import CampaignContext
from app.authorization.dependencies import get_campaign_export_context
from app.backup_downloads import (
    BINARY_DOWNLOAD_RESPONSE,
    backup_file_response,
)
from app.database import get_session
from app.file_storage import validate_client_filename
from app.models.api import CampaignRead
from app.services.campaign_backups import (
    MAX_BACKUP_UPLOAD_BYTES,
    CampaignBackupService,
)


router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)


@router.get(
    "/{campaign_id}/backup/export",
    response_class=FileResponse,
    responses=BINARY_DOWNLOAD_RESPONSE,
)
def export_campaign_backup(
    context: CampaignContext = Depends(get_campaign_export_context),
) -> FileResponse:
    archive = CampaignBackupService(
        context.db,
        context.user,
    ).export(context)
    return backup_file_response(archive)


@router.post("/backup/import")
async def import_campaign_backup(
    backup: UploadFile = File(...),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> CampaignRead:
    validate_client_filename(
        backup.filename,
        required_suffix=".backup",
    )
    raw_data = await backup.read(MAX_BACKUP_UPLOAD_BYTES + 1)
    if len(raw_data) > MAX_BACKUP_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Backup archive is too large",
        )
    return CampaignBackupService(db, user).import_archive(
        raw_data
    )
