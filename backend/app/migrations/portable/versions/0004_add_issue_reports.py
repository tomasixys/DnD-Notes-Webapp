"""Add moderated issue reports.

Revision ID: 0004_add_issue_reports
Revises: 0003_add_roll_user
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_issue_reports"
down_revision = "0003_add_roll_user"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "issue_report" in _table_names():
        return

    op.create_table(
        "issue_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=5000), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "acknowledged",
                "resolved",
                "rejected",
                name="issue_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("reporter_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"],
            ["app_user.id"],
            name="fk_issue_report_reporter_user_id_app_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["app_user.id"],
            name="fk_issue_report_reviewed_by_user_id_app_user",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_issue_report_status",
        "issue_report",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_issue_report_reporter_user_id",
        "issue_report",
        ["reporter_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_issue_report_reviewed_by_user_id",
        "issue_report",
        ["reviewed_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    if "issue_report" not in _table_names():
        return
    op.drop_table("issue_report")
