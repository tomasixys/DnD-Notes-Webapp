from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import ApplicationSettings, DeploymentMode
from app.models.database import Campaign, Installation


class InstallationStateError(RuntimeError):
    """Raised when persisted installation state conflicts with launch mode."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InstallationService:
    def __init__(
        self,
        db: Session,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.id_factory = id_factory or (lambda: str(uuid4()))
        self.clock = clock or utc_now

    def ensure(
        self,
        settings: ApplicationSettings,
    ) -> Installation:
        installation = self.db.get(Installation, 1)
        if installation is not None:
            self._validate_mode(installation, settings)
            return installation

        if self._has_legacy_campaign_data():
            if settings.installation.mode is not DeploymentMode.LOCAL:
                raise InstallationStateError(
                    "An existing pre-authentication database can only be "
                    "claimed by local mode. Move it to hosted mode through "
                    "the explicit migration/import workflow."
                )

        installation = self._build_installation(settings)
        self.db.add(installation)
        try:
            self.db.commit()
            self.db.refresh(installation)
            return installation
        except IntegrityError:
            # A second process may have initialized the singleton first.
            self.db.rollback()
            installation = self.db.get(Installation, 1)
            if installation is None:
                raise
            self._validate_mode(installation, settings)
            return installation

    def _has_legacy_campaign_data(self) -> bool:
        return (
            self.db.exec(select(Campaign.id).limit(1)).first()
            is not None
        )

    def _build_installation(
        self,
        settings: ApplicationSettings,
    ) -> Installation:
        return Installation(
            installation_id=self.id_factory(),
            mode=settings.installation.mode.value,
            initialized_at=self.clock(),
        )

    @staticmethod
    def _validate_mode(
        installation: Installation,
        settings: ApplicationSettings,
    ) -> None:
        requested_mode = settings.installation.mode.value
        if installation.mode != requested_mode:
            raise InstallationStateError(
                "Installation mode mismatch: database is "
                f"'{installation.mode}' but launch configuration requests "
                f"'{requested_mode}'. Mode changes require an explicit "
                "migration."
            )
