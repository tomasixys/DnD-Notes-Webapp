from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import HTTPException, UploadFile

from app.app_paths import get_uploads_dir

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def build_upload_url(relative_path: str) -> str:
    relative_path = relative_path.replace("\\", "/")
    return f"uploads/{relative_path}"


def save_campaign_image(campaign_id: int, file: UploadFile) -> str:
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type. Use jpg, png, webp, or gif.",
        )

    extension = ALLOWED_IMAGE_CONTENT_TYPES[file.content_type]

    relative_dir = Path("campaigns") / str(campaign_id)
    absolute_dir = get_uploads_dir() / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    relative_path = relative_dir / filename
    absolute_path = get_uploads_dir() / relative_path

    bytes_written = 0

    with absolute_path.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            bytes_written += len(chunk)

            if bytes_written > MAX_IMAGE_SIZE_BYTES:
                buffer.close()
                absolute_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=400,
                    detail="Image is too large. Maximum size is 5 MB.",
                )

            buffer.write(chunk)

    return relative_path.as_posix()


def delete_uploaded_file(relative_path: str | None) -> None:
    if not relative_path:
        return

    uploads_dir = get_uploads_dir()
    absolute_path = (uploads_dir / relative_path).resolve()

    try:
        absolute_path.relative_to(uploads_dir.resolve())
    except ValueError:
        return

    absolute_path.unlink(missing_ok=True)