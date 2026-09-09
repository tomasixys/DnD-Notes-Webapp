from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.auth.dependencies import (
    client_ip,
    get_auth_settings,
    get_session_secret,
    require_current_user,
)
from app.auth.enums import SecurityEventType
from app.auth.events import SecurityEventService
from app.auth.models import User
from app.auth.throttling import LoginThrottleService, source_digest
from app.authorization.context import CampaignContext
from app.authorization.dependencies import get_membership_manage_context
from app.authorization.invitations import (
    INVALID_CAMPAIGN_INVITATION,
    CampaignInvitationError,
    CampaignInvitationService,
)
from app.authorization.schemas import (
    CampaignInvitationAccept,
    CampaignInvitationAcceptanceRead,
    CampaignInvitationCreate,
    CampaignInvitationRead,
    IssuedCampaignInvitationRead,
)
from app.config import ApplicationSettings
from app.database import get_session


router = APIRouter(tags=["campaign-invitations"])


def invitation_service(
    db: Session,
    user: User,
) -> CampaignInvitationService:
    return CampaignInvitationService(db, user)


@router.get(
    "/api/campaigns/{campaign_id}/invitations",
)
def list_campaign_invitations(
    context: CampaignContext = Depends(get_membership_manage_context),
    settings: ApplicationSettings = Depends(get_auth_settings),
) -> list[CampaignInvitationRead]:
    return invitation_service(
        context.db,
        context.user,
    ).list_for_campaign(context)


@router.post(
    "/api/campaigns/{campaign_id}/invitations",
)
def create_campaign_invitation(
    payload: CampaignInvitationCreate,
    context: CampaignContext = Depends(get_membership_manage_context),
    settings: ApplicationSettings = Depends(get_auth_settings),
) -> IssuedCampaignInvitationRead:
    try:
        return invitation_service(
            context.db,
            context.user,
        ).issue(
            context,
            payload.username,
            payload.role,
            lifetime_minutes=(
                settings.security.campaign_invitation_lifetime_minutes
            ),
        )
    except CampaignInvitationError as error:
        context.db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/api/campaigns/{campaign_id}/invitations/"
    "{invitation_id}/replace",
)
def replace_campaign_invitation(
    invitation_id: int,
    context: CampaignContext = Depends(get_membership_manage_context),
    settings: ApplicationSettings = Depends(get_auth_settings),
) -> IssuedCampaignInvitationRead:
    try:
        return invitation_service(
            context.db,
            context.user,
        ).replace(
            context,
            invitation_id,
            lifetime_minutes=(
                settings.security.campaign_invitation_lifetime_minutes
            ),
        )
    except CampaignInvitationError as error:
        context.db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete(
    "/api/campaigns/{campaign_id}/invitations/{invitation_id}",
)
def revoke_campaign_invitation(
    invitation_id: int,
    context: CampaignContext = Depends(get_membership_manage_context),
    settings: ApplicationSettings = Depends(get_auth_settings),
) -> CampaignInvitationRead:
    try:
        return invitation_service(
            context.db,
            context.user,
        ).revoke(context, invitation_id)
    except CampaignInvitationError as error:
        context.db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/api/campaign-invitations/pending")
def list_pending_campaign_invitations(
    user: User = Depends(require_current_user),
    settings: ApplicationSettings = Depends(get_auth_settings),
    db: Session = Depends(get_session),
) -> list[CampaignInvitationRead]:
    return invitation_service(db, user).list_pending()


@router.post("/api/campaign-invitations/accept")
def accept_campaign_invitation(
    payload: CampaignInvitationAccept,
    request: Request,
    settings: ApplicationSettings = Depends(get_auth_settings),
    session_secret: str = Depends(get_session_secret),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> CampaignInvitationAcceptanceRead:
    security = settings.security
    digest = source_digest(
        f"campaign-invitation:{client_ip(request)}",
        session_secret,
    )
    throttle = LoginThrottleService(
        db,
        failure_limit=security.invitation_failure_limit,
        window_seconds=security.invitation_failure_window_seconds,
        lock_seconds=security.invitation_lock_seconds,
    )
    events = SecurityEventService(db)
    if not throttle.is_allowed(digest):
        events.record(
            SecurityEventType.MEMBERSHIP_CHANGED,
            user_id=user.id,
            actor_user_id=user.id,
            source_digest=digest,
            reason="action=invitation_acceptance_throttled",
        )
        db.commit()
        raise HTTPException(
            status_code=429,
            detail=INVALID_CAMPAIGN_INVITATION,
        )

    try:
        accepted = invitation_service(db, user).accept(
            payload.token.get_secret_value()
        )
    except CampaignInvitationError as error:
        db.rollback()
        throttled = throttle.record_failure(digest)
        events.record(
            SecurityEventType.MEMBERSHIP_CHANGED,
            user_id=user.id,
            actor_user_id=user.id,
            source_digest=digest,
            reason=(
                "action=invitation_acceptance_throttled"
                if throttled
                else "action=invitation_acceptance_failed"
            ),
        )
        db.commit()
        raise HTTPException(status_code=400, detail=str(error)) from error

    throttle.record_success(digest)
    db.commit()
    return accepted


@router.post("/api/campaign-invitations/{invitation_id}/accept")
def accept_pending_campaign_invitation(
    invitation_id: int,
    user: User = Depends(require_current_user),
    settings: ApplicationSettings = Depends(get_auth_settings),
    db: Session = Depends(get_session),
) -> CampaignInvitationAcceptanceRead:
    try:
        return invitation_service(db, user).accept(invitation_id=invitation_id)
    except CampaignInvitationError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=INVALID_CAMPAIGN_INVITATION) from error


@router.post("/api/campaign-invitations/{invitation_id}/decline")
def decline_pending_campaign_invitation(
    invitation_id: int,
    user: User = Depends(require_current_user),
    settings: ApplicationSettings = Depends(get_auth_settings),
    db: Session = Depends(get_session),
) -> CampaignInvitationRead:
    try:
        return invitation_service(db, user).decline(invitation_id)
    except CampaignInvitationError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=INVALID_CAMPAIGN_INVITATION) from error
