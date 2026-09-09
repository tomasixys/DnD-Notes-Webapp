from collections.abc import Callable

from fastapi import Depends, Request
from sqlmodel import Session

from app.auth.dependencies import require_current_user
from app.auth.models import User
from app.authorization.context import CampaignContext
from app.authorization.enums import CampaignCapability
from app.database import get_session


def get_campaign_context(
    campaign_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    request: Request = None,
) -> CampaignContext:
    context = CampaignContext.resolve(db, campaign_id, user)
    client_instance_id = (
        request.headers.get("X-Client-Instance", "").strip()
        if request is not None
        else ""
    )
    context.client_instance_id = client_instance_id[:64] or None
    context.require(CampaignCapability.CAMPAIGN_READ)
    return context


get_campaign_context.__campaign_authorization__ = (
    CampaignCapability.CAMPAIGN_READ
)


def require_capability(
    capability: CampaignCapability,
) -> Callable[..., CampaignContext]:
    def dependency(
        context: CampaignContext = Depends(get_campaign_context),
    ) -> CampaignContext:
        context.require(capability)
        return context

    dependency.__name__ = (
        "require_" + capability.value.replace(".", "_")
    )
    dependency.__campaign_authorization__ = capability
    return dependency


get_shared_read_context = require_capability(
    CampaignCapability.SHARED_RESOURCE_READ
)
get_shared_write_context = require_capability(
    CampaignCapability.SHARED_RESOURCE_WRITE
)
get_campaign_update_context = require_capability(
    CampaignCapability.CAMPAIGN_UPDATE
)
get_campaign_delete_context = require_capability(
    CampaignCapability.CAMPAIGN_DELETE
)
get_campaign_export_context = require_capability(
    CampaignCapability.CAMPAIGN_EXPORT
)
get_membership_read_context = require_capability(
    CampaignCapability.MEMBERSHIP_READ
)
get_membership_manage_context = require_capability(
    CampaignCapability.MEMBERSHIP_MANAGE
)
