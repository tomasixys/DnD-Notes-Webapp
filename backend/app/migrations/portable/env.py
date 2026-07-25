from alembic import context
from sqlmodel import SQLModel

# Importing the database models registers every table with SQLModel metadata.
from app.models import database as database_models  # noqa: F401


connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError(
        "DnD Notes migrations require an application-managed connection"
    )

context.configure(
    connection=connection,
    target_metadata=SQLModel.metadata,
    compare_type=True,
    render_as_batch=connection.dialect.name == "sqlite",
)

with context.begin_transaction():
    context.run_migrations()
