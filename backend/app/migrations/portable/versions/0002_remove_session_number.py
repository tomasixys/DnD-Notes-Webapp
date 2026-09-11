"""Remove stored episode session numbers.

Revision ID: 0002_remove_session_number
Revises: 0001_current_schema
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_remove_session_number"
down_revision = "0001_current_schema"
branch_labels = None
depends_on = None


def _sessionnote_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "sessionnote" not in inspector.get_table_names():
        return set()
    return {
        column["name"]
        for column in inspector.get_columns("sessionnote")
    }


def _sessionnote_indexes() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        index["name"]
        for index in inspector.get_indexes("sessionnote")
        if index["name"]
    }


def upgrade() -> None:
    if "session_number" not in _sessionnote_columns():
        return

    with op.batch_alter_table("sessionnote") as batch_op:
        if "ix_sessionnote_session_number" in _sessionnote_indexes():
            batch_op.drop_index("ix_sessionnote_session_number")
        batch_op.drop_column("session_number")


def downgrade() -> None:
    if not _sessionnote_columns() or "session_number" in _sessionnote_columns():
        return

    with op.batch_alter_table("sessionnote") as batch_op:
        batch_op.add_column(
            sa.Column("session_number", sa.Integer(), nullable=True)
        )
    op.execute(
        "UPDATE sessionnote SET session_number = id "
        "WHERE session_number IS NULL"
    )
    with op.batch_alter_table("sessionnote") as batch_op:
        batch_op.alter_column(
            "session_number",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_index(
            "ix_sessionnote_session_number",
            ["session_number"],
            unique=False,
        )
