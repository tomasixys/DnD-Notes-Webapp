"""Create the current cross-database schema baseline.

Revision ID: 0001_current_schema
Revises:
Create Date: 2026-07-23
"""

from alembic import op
from sqlmodel import SQLModel

# Register all current tables before creating the baseline.
from app.auth import models as auth_models  # noqa: F401
from app.authorization import models as authorization_models  # noqa: F401
from app.models import database as database_models  # noqa: F401


revision = "0001_current_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    SQLModel.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    SQLModel.metadata.drop_all(bind=op.get_bind())
