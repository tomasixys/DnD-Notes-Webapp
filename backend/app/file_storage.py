import re
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import ZipFile

from fastapi import HTTPException, UploadFile
from app.app_paths import get_uploads_dir

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def build_upload_url(relative_path: str) -> str:
    relative_path = relative_path.replace("\\", "/")
    return f"uploads/{relative_path}"


def save_image_from_uploadfile(campaign_id: int, file: UploadFile) -> str:
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type. Use jpg, png, webp, or gif.",
        )

    extension = ALLOWED_IMAGE_CONTENT_TYPES[file.content_type]
    data = file.file.read(MAX_IMAGE_SIZE_BYTES + 1)
    return write_image_from_bytes(campaign_id, extension, data)


def write_image_from_bytes(
    campaign_id: int,
    extension: str,
    data: bytes,
) -> str:
    extension = extension.lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: '{extension}'. Use jpg, png, webp, or gif.",
        )

    if len(data) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Image is too large.",
        )

    relative_dir = Path("campaigns") / str(campaign_id)
    absolute_dir = get_uploads_dir() / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    relative_path = relative_dir / filename
    absolute_path = get_uploads_dir() / relative_path

    absolute_path.write_bytes(data)
    return relative_path.as_posix()


def delete_uploaded_file(relative_path: str | None) -> None:
    absolute_path = get_uploaded_file_path(relative_path)
    if absolute_path is not None:
        absolute_path.unlink(missing_ok=True)


def get_uploaded_file_path(relative_path: str) -> Path | None:
    uploads_dir = get_uploads_dir().resolve()
    absolute_path = (uploads_dir / relative_path).resolve()

    try:
        absolute_path.relative_to(uploads_dir)
        return absolute_path
    except ValueError:
        return None
    
def make_backup_archive_path(campaign_name: str) -> tuple[Path, str]:
    slug = slugify_filename(campaign_name)
    filename = f"{slug}-backup-{uuid4().hex}.backup"
    relative_path = Path("campaigns") / filename
    absolute_path = get_uploads_dir() / relative_path

    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    return absolute_path, relative_path.as_posix()

def add_upload_to_archive(
    archive: ZipFile,
    uploaded_relative_path: str,
    archive_path: str,
) -> str:
    source_path = get_uploaded_file_path(uploaded_relative_path)

    if source_path is None or not source_path.exists() or not source_path.is_file():
        return ""

    archive.write(source_path, archive_path)
    return archive_path

def is_safe_archive_member_path(path: str) -> bool:
    archive_path = PurePosixPath(path)

    if archive_path.is_absolute() or ".." in archive_path.parts:
        return False

    return True


def slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or "campaign"


def read_archive_member(archive: ZipFile, member_path: str) -> bytes:
    if not member_path:
        return b""
    filepath = Path(member_path).as_posix()
    if not is_safe_archive_member_path(filepath):
        raise HTTPException(status_code=400, detail="Invalid backup archive path")

    try:
        member_info = archive.getinfo(filepath)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Missing archive member: {filepath}")

    if member_info.file_size > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Backup image is too large")

    return archive.read(filepath)