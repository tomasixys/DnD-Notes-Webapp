from sqlmodel import SQLModel, create_engine, Session
from app.app_paths import get_database_path

sqlite_file_name = "notes.db"
sqlite_url = f"sqlite:///{get_database_path()}"

engine = create_engine(
    sqlite_url,
    echo=True,
    connect_args={"check_same_thread": False},
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session