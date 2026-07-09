from sqlalchemy import event
from sqlmodel import SQLModel, create_engine, Session

from app.app_paths import get_database_path

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
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session