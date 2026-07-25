import argparse
import getpass
import json
import shutil
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.app_paths import (
    configure_app_data_dir,
    get_app_data_dir,
    get_uploads_dir,
)
from app.auth.administration import (
    IdentityAdminError,
    IdentityAdminService,
)
from app.auth.passwords import CredentialError
from app.config import (
    ApplicationSettings,
    ConfigurationError,
    DeploymentMode,
    StorageBackend,
    load_runtime_settings,
)
from app.database import create_database_engine, create_db_and_tables
from app.instance_lock import InstanceLock, InstanceLockError
from app.models.database import Campaign, Installation
from app.services.campaign_backups import CampaignBackupService
from app.services.installations import InstallationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Offline DnD Notes inspection and recovery export. "
            "The normal server must be stopped."
        )
    )
    parser.add_argument("--config", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "inspect",
        help="Print non-secret installation and campaign summary data.",
    )
    export = commands.add_parser(
        "export",
        help="Export one campaign from filesystem-backed storage.",
    )
    export.add_argument("--campaign-id", type=int, required=True)
    export.add_argument("--output", type=Path, required=True)
    create_admin = commands.add_parser(
        "create-admin",
        help="Create the first hosted system administrator.",
    )
    create_admin.add_argument("--username", required=True)
    reset_password = commands.add_parser(
        "reset-password",
        help="Reset one hosted local account password and revoke sessions.",
    )
    reset_password.add_argument("--username", required=True)
    return parser.parse_args()


def inspect_installation(settings: ApplicationSettings) -> dict:
    engine = create_database_engine(settings)
    try:
        with Session(engine) as db:
            installation = db.get(Installation, 1)
            if installation is None:
                raise RuntimeError(
                    "Database has no installation record; normal startup "
                    "must initialize or migrate it first."
                )
            campaign_count = db.exec(
                select(func.count()).select_from(Campaign)
            ).one()
            campaigns = db.exec(
                select(Campaign).order_by(Campaign.id)
            ).all()
            return {
                "installation_id": installation.installation_id,
                "mode": installation.mode,
                "initialized_at": installation.initialized_at.isoformat(),
                "campaign_count": campaign_count,
                "campaigns": [
                    {"id": campaign.id, "name": campaign.name}
                    for campaign in campaigns
                ],
            }
    finally:
        engine.dispose()


def export_campaign(
    settings: ApplicationSettings,
    campaign_id: int,
    output: Path,
) -> Path:
    if settings.storage.backend is not StorageBackend.FILESYSTEM:
        raise RuntimeError(
            "Offline campaign export currently requires filesystem storage. "
            "Use the infrastructure disaster-recovery process for object "
            "storage."
        )

    output = output.expanduser().resolve()
    if output.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing output: {output}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)

    engine = create_database_engine(settings)
    generated_path: Path | None = None
    try:
        with Session(engine) as db:
            result = CampaignBackupService(db).export(campaign_id)
            relative_path = result.backup_url.removeprefix("uploads/")
            generated_path = get_uploads_dir() / relative_path
            shutil.copy2(generated_path, output)
        return output
    finally:
        if generated_path is not None:
            generated_path.unlink(missing_ok=True)
        engine.dispose()


def prompt_new_password() -> str:
    password = getpass.getpass("New password: ")
    confirmation = getpass.getpass("Confirm new password: ")
    if password != confirmation:
        raise CredentialError("Password confirmation does not match.")
    return password


def create_initial_admin(
    settings: ApplicationSettings,
    *,
    username: str,
    password: str,
) -> str:
    if settings.installation.mode is not DeploymentMode.HOSTED:
        raise IdentityAdminError(
            "create-admin is available only for hosted installations."
        )
    engine = create_db_and_tables(settings)
    try:
        with Session(engine) as db:
            InstallationService(db).ensure(settings)
            admin = IdentityAdminService(db).create_initial_admin(
                username,
                password,
            )
            return admin.username
    finally:
        engine.dispose()


def reset_local_password(
    settings: ApplicationSettings,
    *,
    username: str,
    password: str,
) -> str:
    if settings.installation.mode is not DeploymentMode.HOSTED:
        raise IdentityAdminError(
            "reset-password is available only for hosted installations."
        )
    engine = create_db_and_tables(settings)
    try:
        with Session(engine) as db:
            InstallationService(db).ensure(settings)
            user = IdentityAdminService(db).reset_password(
                username,
                password,
            )
            return user.username
    finally:
        engine.dispose()


def main() -> None:
    args = parse_args()
    settings = load_runtime_settings(args.config)
    configure_app_data_dir(settings.storage.path)
    lock_path = get_app_data_dir() / "instance.lock"

    with InstanceLock(lock_path):
        if args.command == "inspect":
            print(
                json.dumps(
                    inspect_installation(settings),
                    indent=2,
                    sort_keys=True,
                )
            )
            return
        if args.command == "create-admin":
            username = create_initial_admin(
                settings,
                username=args.username,
                password=prompt_new_password(),
            )
            print(f"Created system administrator: {username}")
            return
        if args.command == "reset-password":
            username = reset_local_password(
                settings,
                username=args.username,
                password=prompt_new_password(),
            )
            print(
                f"Reset password and revoked sessions for: {username}"
            )
            return

        exported_path = export_campaign(
            settings,
            args.campaign_id,
            args.output,
        )
        print(f"Campaign backup exported to {exported_path}")


if __name__ == "__main__":
    try:
        main()
    except (
        ConfigurationError,
        CredentialError,
        IdentityAdminError,
        InstanceLockError,
        RuntimeError,
        SQLAlchemyError,
    ) as error:
        raise SystemExit(f"Maintenance error: {error}") from error
