from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session

from app.auth.dependencies import (
    AuthContext,
    client_ip,
    get_auth_settings,
    require_auth_context,
    require_csrf_context,
    session_service,
)
from app.auth.login import AuthenticationService
from app.auth.schemas import (
    AuthSessionRead,
    AuthUserRead,
    LoginRequest,
    SessionMutationRead,
)
from app.config import ApplicationSettings
from app.database import get_session


router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"],
)

INVALID_CREDENTIALS = "Invalid username or password."


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: ApplicationSettings = Depends(get_auth_settings),
    db: Session = Depends(get_session),
) -> AuthSessionRead:
    security = settings.security
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
        db.commit()
        raise HTTPException(
            status_code=401,
            detail=INVALID_CREDENTIALS,
        )

    issued = session_service(db, settings).create(
        user,
        user_agent=request.headers.get("user-agent"),
        client_ip=client_ip(request),
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
