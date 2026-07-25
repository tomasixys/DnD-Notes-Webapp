from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.services.campaign_backups import CampaignBackupArchive


BINARY_DOWNLOAD_RESPONSE = {
    200: {
        "content": {
            "application/octet-stream": {
                "schema": {
                    "type": "string",
                    "format": "binary",
                }
            }
        },
        "description": "Authorized campaign backup archive.",
    }
}


def backup_file_response(
    archive: CampaignBackupArchive,
) -> FileResponse:
    return FileResponse(
        archive.path,
        media_type="application/octet-stream",
        filename=archive.filename,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(
            archive.path.unlink,
            missing_ok=True,
        ),
    )
