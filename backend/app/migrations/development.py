"""Temporary schema work for the next unreleased database version.

Development migrations must be idempotent and based on schema inspection
because they run without changing ``PRAGMA user_version``. Before release,
move their final behavior into the next numbered module and restore this
function to a no-op.
"""

from sqlalchemy import inspect, text


def _create_inventory_tables(connection) -> None:
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS inventory ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "campaign_id INTEGER NOT NULL, "
            "name VARCHAR NOT NULL DEFAULT 'Party Inventory', "
            "description VARCHAR NOT NULL DEFAULT '', "
            "FOREIGN KEY(campaign_id) REFERENCES campaign (id) ON DELETE CASCADE"
            ")"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_inventory_campaign_id "
            "ON inventory (campaign_id)"
        )
    )

    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS purse ("
            "inventory_id INTEGER NOT NULL PRIMARY KEY, "
            "FOREIGN KEY(inventory_id) REFERENCES inventory (id) ON DELETE CASCADE"
            ")"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS currencybalance ("
            "purse_id INTEGER NOT NULL, "
            "denomination VARCHAR(2) NOT NULL, "
            "amount INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (purse_id, denomination), "
            "CONSTRAINT currency_denomination "
            "CHECK (denomination IN ('cp', 'sp', 'ep', 'gp', 'pp')), "
            "CONSTRAINT ck_currencybalance_amount_non_negative "
            "CHECK (amount >= 0), "
            "FOREIGN KEY(purse_id) REFERENCES purse (inventory_id) ON DELETE CASCADE"
            ")"
        )
    )

    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS inventoryitem ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "inventory_id INTEGER NOT NULL, "
            "name VARCHAR NOT NULL, "
            "description VARCHAR NOT NULL DEFAULT '', "
            "category VARCHAR(10) NOT NULL DEFAULT 'equipment', "
            "rarity VARCHAR(10), "
            "quantity INTEGER NOT NULL DEFAULT 1, "
            "unit_value_cp INTEGER, "
            "CONSTRAINT item_category "
            "CHECK (category IN ('equipment', 'valuable', 'consumable')), "
            "CONSTRAINT item_rarity "
            "CHECK (rarity IS NULL OR rarity IN ("
            "'common', 'uncommon', 'rare', 'very_rare', 'legendary', 'artifact'"
            ")), "
            "CONSTRAINT ck_inventoryitem_quantity_positive "
            "CHECK (quantity > 0), "
            "CONSTRAINT ck_inventoryitem_unit_value_non_negative "
            "CHECK (unit_value_cp IS NULL OR unit_value_cp >= 0), "
            "FOREIGN KEY(inventory_id) REFERENCES inventory (id) ON DELETE CASCADE"
            ")"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_inventoryitem_inventory_id "
            "ON inventoryitem (inventory_id)"
        )
    )

    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS inventoryaccess ("
            "inventory_id INTEGER NOT NULL, "
            "character_person_id INTEGER NOT NULL, "
            "role VARCHAR(7) NOT NULL DEFAULT 'owner', "
            "PRIMARY KEY (inventory_id, character_person_id), "
            "CONSTRAINT inventory_access_role "
            "CHECK (role IN ('owner', 'manager')), "
            "FOREIGN KEY(inventory_id) REFERENCES inventory (id) ON DELETE CASCADE, "
            "FOREIGN KEY(character_person_id) "
            "REFERENCES characterprofile (person_id) ON DELETE CASCADE"
            ")"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_inventoryaccess_character_person_id "
            "ON inventoryaccess (character_person_id)"
        )
    )


def _add_inventory_columns(connection) -> None:
    item_columns = {
        column["name"]
        for column in inspect(connection).get_columns("inventoryitem")
    }
    if "rarity" not in item_columns:
        connection.execute(
            text(
                "ALTER TABLE inventoryitem ADD COLUMN rarity VARCHAR(10) "
                "CONSTRAINT item_rarity CHECK (rarity IS NULL OR rarity IN ("
                "'common', 'uncommon', 'rare', 'very_rare', 'legendary', 'artifact'"
                "))"
            )
        )


def migrate_development_schema(connection) -> None:
    existing_tables = set(inspect(connection).get_table_names())
    if not {"campaign", "characterprofile"}.issubset(existing_tables):
        return

    if "currencyvalue" in existing_tables:
        connection.execute(text("DROP TABLE currencyvalue"))

    _create_inventory_tables(connection)
    _add_inventory_columns(connection)
