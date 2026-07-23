"""Temporary schema work for the next unreleased database version.

Development migrations must be idempotent and based on schema inspection
because they run without changing ``PRAGMA user_version``. Before release,
move their final behavior into the next numbered module and restore this
function to a no-op.
"""


def migrate_development_schema(connection) -> None:
    pass
