# app_paths.py

from pathlib import Path
from platformdirs import user_data_path

APP_NAME = "DnD Notes"
APP_AUTHOR = "tomasixys"

def get_app_data_dir() -> Path:
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
