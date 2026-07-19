from sqlalchemy import event
from sqlmodel import SQLModel, create_engine, Session

from app.app_paths import get_database_path
from app.migrations import (
    backup_database_before_migration,
    run_database_migrations,
)

sqlite_url = f"sqlite:///{get_database_path()}"

engine = create_engine(
    sqlite_url,
    echo=True,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_and_tables():
    backup_database_before_migration(get_database_path())
    # Explicitly import all database models to populate SQLModel metadata
    from app.models.database import (
        Campaign,
        Tag,
        TagAssignment,
        SessionNote,
        RollEntry,
        Person,
        Location,
        Faction,
    )

    SQLModel.metadata.create_all(engine)
    run_database_migrations(engine)


def get_session():
    with Session(engine) as session:
        yield session
