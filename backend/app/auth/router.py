from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session

from app.auth.accounts import (
    AccountLifecycleError,
    AccountLifecycleService,
    IssuedAccountToken,
)
from app.auth.dependencies import (
    AuthContext,
    client_ip,
    get_auth_settings,
    require_auth_context,
    require_csrf_context,
    session_service,
)
from app.auth.enums import SecurityEventType, SystemRole, UserStatus
from app.auth.events import SecurityEventService
from app.auth.login import AuthenticationService
from app.auth.schemas import (
    AccountMutationRead,
    AccountTokenRequest,
    AuthSessionRead,
    AuthUserRead,
    InviteUserRequest,
    IssuedAccountTokenRead,
    LoginRequest,
    SessionMutationRead,
)
from app.auth.throttling import LoginThrottleService, source_digest
from app.config import ApplicationSettings
from app.database import get_session


router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"],
)

INVALID_CREDENTIALS = "Invalid username or password."
ADMIN_REQUIRED = "System administrator privileges are required."


def get_session_secret(
    settings: ApplicationSettings = Depends(get_auth_settings),
) -> str:
    environment_name = settings.security.session_secret_env or ""
    secret = os.environ.get(environment_name, "")
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=500,
            detail="Hosted session secret is unavailable.",
        )
    return secret


def require_admin_context(
    context: AuthContext = Depends(require_csrf_context),
) -> AuthContext:
    if (
        context.user.status is not UserStatus.ACTIVE
        or context.user.system_role is not SystemRole.ADMIN
    ):
        raise HTTPException(status_code=403, detail=ADMIN_REQUIRED)
    return context


def account_service(db: Session) -> AccountLifecycleService:
    return AccountLifecycleService(db)


def issued_token_read(
    issued: IssuedAccountToken,
) -> IssuedAccountTokenRead:
    return IssuedAccountTokenRead(
        user=AuthUserRead.from_user(issued.user),
        token=issued.token,
        expires_at=issued.expires_at,
    )


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: ApplicationSettings = Depends(get_auth_settings),
    session_secret: str = Depends(get_session_secret),
    db: Session = Depends(get_session),
) -> AuthSessionRead:
    security = settings.security
    digest = source_digest(client_ip(request), session_secret)
    throttle = LoginThrottleService(
        db,
        failure_limit=security.login_source_failure_limit,
        window_seconds=security.login_source_window_seconds,
        lock_seconds=security.login_source_lock_seconds,
    )
    events = SecurityEventService(db)
    if not throttle.is_allowed(digest):
        events.record(
            SecurityEventType.LOGIN_SOURCE_THROTTLED,
            source_digest=digest,
        )
        db.commit()
        raise HTTPException(
            status_code=401,
            detail=INVALID_CREDENTIALS,
        )

    authentication = AuthenticationService(
        db,
        failure_limit=security.login_failure_limit,
        initial_lock_seconds=security.login_initial_lock_seconds,
        maximum_lock_seconds=security.login_maximum_lock_seconds,
    )
    user = authentication.authenticate(
        payload.username,
        payload.password.get_secret_value(),
    )
    if user is None:
        throttled = throttle.record_failure(digest)
        events.record(
            (
                SecurityEventType.LOGIN_SOURCE_THROTTLED
                if throttled
                else SecurityEventType.LOGIN_FAILED
            ),
            source_digest=digest,
        )
        db.commit()
        raise HTTPException(
            status_code=401,
            detail=INVALID_CREDENTIALS,
        )

    throttle.record_success(digest)
    issued = session_service(db, settings).create(
        user,
        user_agent=request.headers.get("user-agent"),
        client_ip=client_ip(request),
    )
    events.record(
        SecurityEventType.LOGIN_SUCCEEDED,
        user_id=user.id,
        source_digest=digest,
    )
    db.commit()
    response.set_cookie(
        key=security.cookie_name,
        value=issued.session_token,
        max_age=security.session_absolute_lifetime_minutes * 60,
        path="/",
        secure=security.cookie_secure,
        httponly=True,
        samesite=security.cookie_samesite.value,
    )
    return AuthSessionRead(
        user=AuthUserRead.from_user(user),
        csrf_token=issued.csrf_token,
    )


@router.post("/activate")
def activate_account(
    payload: AccountTokenRequest,
    db: Session = Depends(get_session),
) -> AccountMutationRead:
    try:
        user = account_service(db).activate(
            payload.token.get_secret_value(),
            payload.password.get_secret_value(),
        )
    except AccountLifecycleError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return AccountMutationRead(
        user=AuthUserRead.from_user(user),
        message="Account activated.",
    )


@router.post("/reset-password")
def reset_password(
    payload: AccountTokenRequest,
    db: Session = Depends(get_session),
) -> AccountMutationRead:
    try:
        user = account_service(db).reset_password(
            payload.token.get_secret_value(),
            payload.password.get_secret_value(),
        )
    except AccountLifecycleError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return AccountMutationRead(
        user=AuthUserRead.from_user(user),
        message="Password reset.",
    )


@router.post("/admin/invitations")
def invite_user(
    payload: InviteUserRequest,
    settings: ApplicationSettings = Depends(get_auth_settings),
    context: AuthContext = Depends(require_admin_context),
    db: Session = Depends(get_session),
) -> IssuedAccountTokenRead:
    try:
        issued = account_service(db).invite_user(
            context.user,
            payload.username,
            display_name=payload.display_name,
            lifetime_minutes=(
                settings.security.activation_token_lifetime_minutes
            ),
        )
    except AccountLifecycleError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    return issued_token_read(issued)


@router.post("/admin/users/{user_id}/password-reset")
def issue_password_reset(
    user_id: int,
    settings: ApplicationSettings = Depends(get_auth_settings),
    context: AuthContext = Depends(require_admin_context),
    db: Session = Depends(get_session),
) -> IssuedAccountTokenRead:
    try:
        issued = account_service(db).issue_password_reset(
            context.user,
            user_id,
            lifetime_minutes=(
                settings.security.password_reset_token_lifetime_minutes
            ),
        )
    except AccountLifecycleError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(error)) from error
    return issued_token_read(issued)


@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    context: AuthContext = Depends(require_admin_context),
    db: Session = Depends(get_session),
) -> AccountMutationRead:
    try:
        user = account_service(db).delete_user(context.user, user_id)
    except AccountLifecycleError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return AccountMutationRead(
        user=AuthUserRead.from_user(user),
        message="Account deleted.",
    )


@router.get("/session")
def current_session(
    context: AuthContext = Depends(require_auth_context),
    db: Session = Depends(get_session),
) -> AuthSessionRead:
    csrf_token = context.service.rotate_csrf(context.session)
    db.commit()
    return AuthSessionRead(
        user=AuthUserRead.from_user(context.user),
        csrf_token=csrf_token,
    )


@router.post("/logout")
def logout(
    response: Response,
    settings: ApplicationSettings = Depends(get_auth_settings),
    context: AuthContext = Depends(require_csrf_context),
    db: Session = Depends(get_session),
) -> SessionMutationRead:
    context.service.revoke(context.session)
    db.commit()
    response.delete_cookie(
        key=settings.security.cookie_name,
        path="/",
    )
    return SessionMutationRead(
        message="Logged out.",
        revoked_sessions=1,
    )


@router.post("/logout-all")
def logout_all(
    response: Response,
    settings: ApplicationSettings = Depends(get_auth_settings),
    context: AuthContext = Depends(require_csrf_context),
    db: Session = Depends(get_session),
) -> SessionMutationRead:
    revoked = context.service.revoke_all(context.user.id)
    db.commit()
    response.delete_cookie(
        key=settings.security.cookie_name,
        path="/",
    )
    return SessionMutationRead(
        message="Logged out from all sessions.",
        revoked_sessions=revoked,
    )
