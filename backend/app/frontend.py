import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def get_frontend_dist_dir() -> Path:
    """Locate Vite's compiled frontend in source and PyInstaller builds."""
    bundled_dir = Path(__file__).resolve().parent / "frontend_dist"
    if bundled_dir.is_dir():
        return bundled_dir

    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def mount_frontend(app: FastAPI) -> bool:
    """Serve the compiled Vue application, including history-mode routes."""
    frontend_dir = get_frontend_dist_dir().resolve()
    index_file = frontend_dir / "index.html"

    if not index_file.is_file():
        logger.info(
            "Frontend build not found at %s; starting in API-only mode.",
            frontend_dir,
        )
        return False

    assets_dir = frontend_dir / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="frontend-assets",
        )

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_frontend(requested_path: str):
        # API paths should return a normal API 404, not index.html.
        if requested_path == "api" or requested_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")

        requested_file = (frontend_dir / requested_path).resolve()

        try:
            requested_file.relative_to(frontend_dir)
        except ValueError:
            return FileResponse(index_file)

        if requested_file.is_file():
            return FileResponse(requested_file)

        # Vue Router uses HTML5 history mode, so client routes need index.html.
        return FileResponse(index_file)

    logger.info("Serving frontend from %s", frontend_dir)
    return True
