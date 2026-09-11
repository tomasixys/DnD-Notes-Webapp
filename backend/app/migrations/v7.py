"""Migration from schema version 6 to schema version 7.

Version 7 adds installation-wide issue reports with an administrator-controlled
publication status.
"""

from sqlalchemy import inspect, text


def migrate_to_v7(connection) -> None:
    tables = set(inspect(connection).get_table_names())
    if "issue_report" in tables or "app_user" not in tables:
        return

    connection.execute(
        text(
            "CREATE TABLE issue_report ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "title VARCHAR(160) NOT NULL, "
            "description VARCHAR(5000) NOT NULL, "
            "status VARCHAR(12) NOT NULL, "
            "reporter_user_id INTEGER, "
            "reviewed_by_user_id INTEGER, "
            "review_note VARCHAR(1000) NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL, "
            "reviewed_at DATETIME, "
            "CONSTRAINT issue_status CHECK (status IN ("
            "'pending', 'acknowledged', 'resolved', 'rejected'"
            ")), "
            "FOREIGN KEY(reporter_user_id) "
            "REFERENCES app_user (id) ON DELETE SET NULL, "
            "FOREIGN KEY(reviewed_by_user_id) "
            "REFERENCES app_user (id) ON DELETE SET NULL"
            ")"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX ix_issue_report_status "
            "ON issue_report (status)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX ix_issue_report_reporter_user_id "
            "ON issue_report (reporter_user_id)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX ix_issue_report_reviewed_by_user_id "
            "ON issue_report (reviewed_by_user_id)"
        )
    )
