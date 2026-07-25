from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlmodel import Session, create_engine

from app.app_paths import get_database_path
from app.config import (
    ApplicationSettings,
    ConfigurationError,
    DeploymentMode,
)
from app.migrations import (
    backup_database_before_migration,
    run_database_migrations,
)


_engine: Engine | None = None


def resolve_database_url(settings: ApplicationSettings) -> URL:
    database = settings.database
    if database.url_env is not None:
        raw_url = os.environ.get(database.url_env)
        if raw_url is None or not raw_url.strip():
            raise ConfigurationError(
                f"Database URL environment variable "
                f"{database.url_env!r} is not set"
            )
        raw_url = raw_url.strip()
    elif database.url is not None:
        raw_url = database.url
    else:
        raw_url = f"sqlite:///{get_database_path().as_posix()}"

    try:
        url = make_url(raw_url)
    except (ArgumentError, TypeError, ValueError) as error:
        raise ConfigurationError("database URL is invalid") from error

    backend = url.get_backend_name()
    if (
        settings.installation.mode is DeploymentMode.LOCAL
        and backend != "sqlite"
    ):
        raise ConfigurationError(
            "local mode currently supports only SQLite databases"
        )
    if (
        settings.installation.mode is DeploymentMode.HOSTED
        and backend != "postgresql"
    ):
        raise ConfigurationError(
            "hosted mode requires a PostgreSQL database URL"
        )
    if (
        settings.installation.mode is DeploymentMode.HOSTED
        and url.drivername != "postgresql+psycopg"
    ):
        raise ConfigurationError(
            "hosted mode requires the postgresql+psycopg driver"
        )
    return url


def create_database_engine(settings: ApplicationSettings) -> Engine:
    url = resolve_database_url(settings)
    engine_options: dict[str, object] = {
        "echo": settings.database.echo,
        "pool_pre_ping": settings.database.pool_pre_ping,
    }
    if url.get_backend_name() == "sqlite":
        engine_options["connect_args"] = {"check_same_thread": False}
    else:
        engine_options["pool_recycle"] = (
            settings.database.pool_recycle_seconds
        )

    engine = create_engine(url, **engine_options)
    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection,
            connection_record,
        ) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def _sqlite_database_path(engine: Engine) -> Path | None:
    if engine.dialect.name != "sqlite":
        return None
    database = engine.url.database
    if database in {None, "", ":memory:"}:
        return None
    return Path(database)


def _load_database_models() -> None:
    # Explicit imports populate SQLModel metadata in source and frozen builds.
    from app.models.database import (  # noqa: F401
        BackstoryNote,
        AccountToken,
        AuthSession,
        Campaign,
        CharacterNote,
        CharacterProfile,
        CurrencyBalance,
        Faction,
        Installation,
        Inventory,
        InventoryAccess,
        InventoryItem,
        Location,
        PasswordCredential,
        Person,
        Purse,
        RollEntry,
        SessionNote,
        Tag,
        TagAssignment,
        User,
    )


def create_db_and_tables(settings: ApplicationSettings) -> Engine:
    global _engine

    candidate = create_database_engine(settings)
    try:
        database_path = _sqlite_database_path(candidate)
        if database_path is not None:
            backup_database_before_migration(database_path)

        _load_database_models()
        run_database_migrations(candidate)
    except Exception:
        candidate.dispose()
        raise

    if _engine is not None:
        _engine.dispose()
    _engine = candidate
    return candidate


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError(
            "Database engine has not been initialized by application startup"
        )
    return _engine


def get_session():
    with Session(get_engine()) as session:
        yield session
