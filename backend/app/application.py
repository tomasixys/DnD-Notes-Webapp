import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlmodel import Session

from app.app_paths import (
    configure_app_data_dir,
    get_app_data_dir,
    get_campaign_images_dir,
    get_uploads_dir,
    get_transient_backups_dir,
)
from app.auth.administration import IdentityBootstrapService
from app.auth.middleware import install_authentication_middleware
from app.auth import router as auth_router
from app.authorization.bootstrap import MembershipBootstrapService
from app.authorization.route_audit import (
    audit_campaign_route_authorization,
)
from app.config import (
    ApplicationSettings,
    DeploymentMode,
    load_runtime_settings,
    validate_build_profile,
)
from app.database import create_db_and_tables
from app.frontend import mount_frontend
from app.file_storage import (
    BACKUP_EXPIRY_SECONDS,
    cleanup_expired_backup_archives,
)
from app.instance_lock import InstanceLock
from app.observability import install_observability
from app.request_limits import install_request_limits
from app.routers import (
    assets,
    campaign_backups,
    campaigns,
    authorization_admin,
    characters,
    changes,
    episodes,
    factions,
    health,
    inventory,
    invitations,
    issues,
    locations,
    people,
    rolls,
    search,
    memberships,
    notifications,
)
from app.services.installations import InstallationService


def initialize_app_storage() -> None:
    get_app_data_dir()
    get_uploads_dir()
    get_campaign_images_dir()
    get_transient_backups_dir()


async def cleanup_transient_backups_periodically() -> None:
    while True:
        await asyncio.sleep(BACKUP_EXPIRY_SECONDS)
        cleanup_expired_backup_archives()


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
    configure_app_data_dir(settings.storage.path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        initialize_app_storage()
        lock = InstanceLock(get_app_data_dir() / "instance.lock")
        with lock:
            cleanup_expired_backup_archives()
            engine = create_db_and_tables(settings)
            cleanup_task = asyncio.create_task(
                cleanup_transient_backups_periodically()
            )
            try:
                with Session(engine) as db:
                    InstallationService(db).ensure(settings)
                    if (
                        settings.installation.mode
                        is DeploymentMode.LOCAL
                    ):
                        IdentityBootstrapService(db).ensure_local_user()
                        MembershipBootstrapService(
                            db
                        ).ensure_local_ownership()
                yield
            finally:
                cleanup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await cleanup_task
                engine.dispose()

    application = FastAPI(
        title="Campaign Notes API",
        lifespan=lifespan,
    )
    application.state.settings = settings
    install_observability(application)
    install_authentication_middleware(application, settings)
    install_request_limits(application, settings)

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
        expose_headers=["Content-Disposition"],
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.server.trusted_hosts,
    )

    application.include_router(health.router)
    application.include_router(auth_router.session_router)
    if settings.installation.mode is DeploymentMode.HOSTED:
        application.include_router(auth_router.router)

    application.include_router(campaigns.router)
    application.include_router(assets.router)
    application.include_router(invitations.router)
    application.include_router(memberships.router)
    application.include_router(campaign_backups.router)
    application.include_router(authorization_admin.router)
    application.include_router(episodes.router)
    application.include_router(people.router)
    application.include_router(locations.router)
    application.include_router(factions.router)
    application.include_router(rolls.router)
    application.include_router(search.router)
    application.include_router(characters.router)
    application.include_router(changes.router)
    application.include_router(inventory.router)
    application.include_router(issues.router)
    application.include_router(notifications.router)
    audit_campaign_route_authorization(application)

    # Keep this after every API router. It contains the catch-all SPA route.
    mount_frontend(application)
    return application
