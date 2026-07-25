# app_paths.py

from pathlib import Path
from platformdirs import user_data_path

APP_NAME = "DnD Notes"
APP_AUTHOR = "tomasixys"
_configured_app_data_dir: Path | None = None


def configure_app_data_dir(path: Path | None) -> None:
    global _configured_app_data_dir
    _configured_app_data_dir = (
        path.expanduser().resolve()
        if path is not None
        else None
    )


def get_app_data_dir() -> Path:
    if _configured_app_data_dir is not None:
        _configured_app_data_dir.mkdir(parents=True, exist_ok=True)
        return _configured_app_data_dir
    return user_data_path(
        appname=APP_NAME,
        appauthor=APP_AUTHOR,
        ensure_exists=True,
    )


def get_database_path() -> Path:
    return get_app_data_dir() / "notes.db"


def get_uploads_dir() -> Path:
    path = get_app_data_dir() / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_campaign_images_dir() -> Path:
    path = get_uploads_dir() / "campaigns"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_transient_backups_dir() -> Path:
    path = get_app_data_dir() / "transient-backups"
    path.mkdir(parents=True, exist_ok=True)
    return path
