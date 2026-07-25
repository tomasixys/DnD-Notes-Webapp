import io
import re
import time
import warnings
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import ZipFile

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageSequence, UnidentifiedImageError

from app.app_paths import get_transient_backups_dir, get_uploads_dir

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_PIXELS = 40_000_000
MAX_ANIMATED_IMAGE_FRAMES = 500
MAX_ANIMATED_IMAGE_TOTAL_PIXELS = 80_000_000
BACKUP_EXPIRY_SECONDS = 60 * 60

IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
    "GIF": ("image/gif", ".gif"),
}


@dataclass(frozen=True)
class StoredImage:
    path: Path
    media_type: str


def build_campaign_asset_url(
    campaign_id: int,
    asset_kind: str,
) -> str:
    return f"campaigns/{campaign_id}/assets/{asset_kind}"


def build_character_asset_url(
    campaign_id: int,
    person_id: int,
) -> str:
    return (
        f"campaigns/{campaign_id}/assets/characters/"
        f"{person_id}/portrait"
    )


def validate_client_filename(
    filename: str | None,
    *,
    required_suffix: str | None = None,
) -> str:
    value = (filename or "").strip()
    if (
        not value
        or len(value) > 255
        or "/" in value
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise HTTPException(status_code=400, detail="Invalid upload filename.")
    if (
        required_suffix is not None
        and not value.casefold().endswith(required_suffix.casefold())
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Upload filename must end with {required_suffix}.",
        )
    return value


def inspect_image_bytes(data: bytes) -> tuple[str, str]:
    if not data:
        raise HTTPException(status_code=400, detail="Image is empty.")
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Image is too large.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                image_format = image.format
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=400,
                        detail="Image dimensions are too large.",
                    )
                image.verify()
            with Image.open(io.BytesIO(data)) as decoded:
                total_pixels = 0
                for frame_index, frame in enumerate(
                    ImageSequence.Iterator(decoded),
                    start=1,
                ):
                    if frame_index > MAX_ANIMATED_IMAGE_FRAMES:
                        raise HTTPException(
                            status_code=400,
                            detail="Animated image has too many frames.",
                        )
                    total_pixels += frame.width * frame.height
                    if total_pixels > MAX_ANIMATED_IMAGE_TOTAL_PIXELS:
                        raise HTTPException(
                            status_code=400,
                            detail="Animated image is too large.",
                        )
                    frame.load()
    except HTTPException:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid or unsafe image data.",
        ) from error

    image_type = IMAGE_FORMATS.get(image_format or "")
    if image_type is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type. Use jpg, png, webp, or gif.",
        )
    return image_type


def save_image_from_uploadfile(campaign_id: int, file: UploadFile) -> str:
    filename = validate_client_filename(file.filename)
    data = file.file.read(MAX_IMAGE_SIZE_BYTES + 1)
    media_type, extension = inspect_image_bytes(data)
    filename_extension = Path(filename).suffix.lower()
    normalized_filename_extension = (
        ".jpg"
        if filename_extension == ".jpeg"
        else filename_extension
    )
    if normalized_filename_extension != extension:
        raise HTTPException(
            status_code=400,
            detail="Image data does not match its filename extension.",
        )
    claimed_type = (file.content_type or "").partition(";")[0].strip().lower()
    if claimed_type != media_type:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image content does not match its content type.",
        )
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

    _, detected_extension = inspect_image_bytes(data)
    normalized_extension = ".jpg" if extension == ".jpeg" else extension
    if normalized_extension != detected_extension:
        raise HTTPException(
            status_code=400,
            detail="Image data does not match its filename extension.",
        )

    relative_dir = Path("campaigns") / str(campaign_id)
    absolute_dir = get_uploads_dir() / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{detected_extension}"
    relative_path = relative_dir / filename
    absolute_path = get_uploads_dir() / relative_path

    absolute_path.write_bytes(data)
    return relative_path.as_posix()


def delete_uploaded_file(relative_path: str | None) -> None:
    if not relative_path:
        return
    absolute_path = get_uploaded_file_path(relative_path)
    if absolute_path is not None:
        absolute_path.unlink(missing_ok=True)


def get_uploaded_file_path(relative_path: str) -> Path | None:
    uploads_dir = get_uploads_dir().resolve()
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return None
    absolute_path = (uploads_dir / candidate).resolve()

    try:
        absolute_path.relative_to(uploads_dir)
        return absolute_path
    except ValueError:
        return None


def resolve_stored_image(relative_path: str) -> StoredImage:
    absolute_path = get_uploaded_file_path(relative_path)
    if (
        absolute_path is None
        or not absolute_path.exists()
        or not absolute_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="Asset not found.")
    if absolute_path.stat().st_size > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Image is too large.")
    media_type, _ = inspect_image_bytes(
        absolute_path.read_bytes()
    )
    return StoredImage(path=absolute_path, media_type=media_type)


def make_backup_archive_path(campaign_name: str) -> tuple[Path, str]:
    cleanup_expired_backup_archives()
    slug = slugify_filename(campaign_name)
    filename = f"{slug}-backup-{uuid4().hex}.backup"
    absolute_path = get_transient_backups_dir() / filename
    return absolute_path, filename


def cleanup_expired_backup_archives(
    *,
    now: float | None = None,
    maximum_age_seconds: int = BACKUP_EXPIRY_SECONDS,
) -> int:
    current_time = time.time() if now is None else now
    removed = 0
    for candidate in get_transient_backups_dir().glob("*.backup"):
        try:
            expired = (
                current_time - candidate.stat().st_mtime
                >= maximum_age_seconds
            )
        except FileNotFoundError:
            continue
        if expired:
            candidate.unlink(missing_ok=True)
            removed += 1
    return removed


def add_upload_to_archive(
    archive: ZipFile,
    uploaded_relative_path: str,
    archive_path: str,
) -> str:
    source_path = get_uploaded_file_path(uploaded_relative_path)

    if (
        source_path is None
        or not source_path.exists()
        or not source_path.is_file()
    ):
        return ""

    resolve_stored_image(uploaded_relative_path)
    archive.write(source_path, archive_path)
    return archive_path


def is_safe_archive_member_path(path: str) -> bool:
    if not path or "\x00" in path or "\\" in path:
        return False
    archive_path = PurePosixPath(path)

    if archive_path.is_absolute() or ".." in archive_path.parts:
        return False

    return True


def slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    slug = slug.strip("-")[:80].rstrip("-_")
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
        raise HTTPException(
            status_code=400,
            detail=f"Missing archive member: {filepath}",
        )

    if member_info.file_size > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Backup image is too large",
        )

    return archive.read(filepath)
