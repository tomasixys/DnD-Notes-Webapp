from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from app.database import get_session
from app.services.campaign_backups import CampaignBackupService


router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
)


@router.get("/{campaign_id}/backup/export")
def export_campaign_backup(
    campaign_id: int,
    db: Session = Depends(get_session),
):
    return CampaignBackupService(db).export(campaign_id)


@router.post("/backup/import")
async def import_campaign_backup(
    backup: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    return CampaignBackupService(db).import_archive(
        await backup.read()
    )
