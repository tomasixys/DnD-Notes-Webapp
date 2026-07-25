from contextlib import asynccontextmanager

from fastapi import FastAPI, staticfiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlmodel import Session

from app.app_paths import (
    configure_app_data_dir,
    get_app_data_dir,
    get_campaign_images_dir,
    get_uploads_dir,
)
from app.config import (
    ApplicationSettings,
    ConfigurationError,
    DeploymentMode,
    load_runtime_settings,
    validate_build_profile,
)
from app.database import create_db_and_tables
from app.frontend import mount_frontend
from app.instance_lock import InstanceLock
from app.routers import (
    campaign_backups,
    campaigns,
    characters,
    episodes,
    factions,
    inventory,
    locations,
    people,
    rolls,
    search,
)
from app.services.installations import InstallationService


def initialize_app_storage() -> None:
    get_app_data_dir()
    get_uploads_dir()
    get_campaign_images_dir()


def create_app(
    settings: ApplicationSettings | None = None,
    *,
    build_profile: DeploymentMode | str | None = None,
) -> FastAPI:
    settings = (
        validate_build_profile(settings, build_profile)
        if settings is not None
        else load_runtime_settings()
    )
    if settings.installation.mode is DeploymentMode.HOSTED:
        raise ConfigurationError(
            "Hosted mode startup is disabled until authentication and "
            "authorization are implemented."
        )

    configure_app_data_dir(settings.storage.path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        initialize_app_storage()
        lock = InstanceLock(get_app_data_dir() / "instance.lock")
        with lock:
            engine = create_db_and_tables(settings)
            try:
                with Session(engine) as db:
                    InstallationService(db).ensure(settings)
                yield
            finally:
                engine.dispose()

    application = FastAPI(
        title="Campaign Notes API",
        lifespan=lifespan,
    )
    application.state.settings = settings

    allowed_origins = ["http://localhost:5173"]
    if (
        settings.installation.mode is DeploymentMode.HOSTED
        and settings.server.public_origin is not None
    ):
        allowed_origins = [settings.server.public_origin]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.server.trusted_hosts,
    )

    application.mount(
        "/api/uploads",
        staticfiles.StaticFiles(directory=get_uploads_dir()),
        name="uploads",
    )

    application.include_router(campaigns.router)
    application.include_router(campaign_backups.router)
    application.include_router(episodes.router)
    application.include_router(people.router)
    application.include_router(locations.router)
    application.include_router(factions.router)
    application.include_router(rolls.router)
    application.include_router(search.router)
    application.include_router(characters.router)
    application.include_router(inventory.router)

    # Keep this after every API router. It contains the catch-all SPA route.
    mount_frontend(application)
    return application
