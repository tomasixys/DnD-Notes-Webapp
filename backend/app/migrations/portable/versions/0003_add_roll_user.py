"""Associate roll entries with users.

Revision ID: 0003_add_roll_user
Revises: 0002_remove_session_number
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_roll_user"
down_revision = "0002_remove_session_number"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rollentry_columns() -> set[str]:
    if "rollentry" not in _table_names():
        return set()
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("rollentry")
    }


def _rollentry_indexes() -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("rollentry")
        if index["name"]
    }


def upgrade() -> None:
    if "rollentry" not in _table_names():
        return

    if "user_id" not in _rollentry_columns():
        with op.batch_alter_table("rollentry") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "user_id",
                    sa.Integer(),
                    nullable=True,
                )
            )
            batch_op.create_foreign_key(
                "fk_rollentry_user_id_app_user",
                "app_user",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if {
        "sessionnote",
        "campaign_membership",
    }.issubset(_table_names()):
        membership_columns = {
            column["name"]
            for column in sa.inspect(op.get_bind()).get_columns(
                "campaign_membership"
            )
        }
        custodial_filter = (
            "AND campaign_membership.is_custodial = FALSE "
            if "is_custodial" in membership_columns
            else ""
        )
        backfill_statement = (
            "UPDATE rollentry SET user_id = ("
            "SELECT campaign_membership.user_id "
            "FROM sessionnote "
            "JOIN campaign_membership ON "
            "campaign_membership.campaign_id = sessionnote.campaign_id "
            "WHERE sessionnote.id = rollentry.session_id "
            "AND campaign_membership.role = 'owner' "
            + custodial_filter
            + "ORDER BY campaign_membership.id LIMIT 1"
            ") WHERE user_id IS NULL"
        )
        op.execute(backfill_statement)

    if "ix_rollentry_user_id" not in _rollentry_indexes():
        op.create_index(
            "ix_rollentry_user_id",
            "rollentry",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    if "user_id" not in _rollentry_columns():
        return

    with op.batch_alter_table("rollentry") as batch_op:
        if "ix_rollentry_user_id" in _rollentry_indexes():
            batch_op.drop_index("ix_rollentry_user_id")
        batch_op.drop_column("user_id")
