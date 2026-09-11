"""Migration from schema version 5 to schema version 6.

Version 6 associates roll entries with the user who recorded them. Existing
rolls are assigned to the campaign's non-custodial owner when one is known.
"""

from sqlalchemy import inspect, text


def _backfill_owner_user_ids(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if not {
        "rollentry",
        "sessionnote",
        "campaign_membership",
    }.issubset(tables):
        return

    membership_columns = {
        column["name"]
        for column in inspector.get_columns("campaign_membership")
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
    connection.execute(text(backfill_statement))


def migrate_to_v6(connection) -> None:
    inspector = inspect(connection)
    if "rollentry" not in inspector.get_table_names():
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("rollentry")
    }
    if "user_id" not in columns:
        connection.execute(
            text(
                "ALTER TABLE rollentry ADD COLUMN user_id INTEGER "
                "REFERENCES app_user(id) ON DELETE SET NULL"
            )
        )

    _backfill_owner_user_ids(connection)

    indexes = {
        index["name"]
        for index in inspect(connection).get_indexes("rollentry")
        if index["name"]
    }
    if "ix_rollentry_user_id" not in indexes:
        connection.execute(
            text(
                "CREATE INDEX ix_rollentry_user_id "
                "ON rollentry (user_id)"
            )
        )
