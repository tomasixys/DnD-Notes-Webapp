"""Compatibility imports for the authorization dependency boundary."""

from app.authorization.dependencies import (  # noqa: F401
    get_campaign_context,
    get_campaign_delete_context,
    get_campaign_export_context,
    get_campaign_update_context,
    get_membership_manage_context,
    get_membership_read_context,
    get_shared_read_context,
    get_shared_write_context,
)
