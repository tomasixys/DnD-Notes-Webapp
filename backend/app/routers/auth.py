from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlmodel import Session

from app.config import ApplicationSettings, DeploymentMode
from app.database import get_session
from app.models.api import (
    AuthSessionRead,
    AuthUserRead,
    LoginRequest,
    SessionMutationRead,
)
from app.models.database import AuthSession, User
from app.services.auth_sessions import AuthSessionService
from app.services.authentication import AuthenticationService


router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"],
)

INVALID_CREDENTIALS = "Invalid username or password."
AUTHENTICATION_REQUIRED = "Authentication required."
CSRF_REQUIRED = "Valid CSRF token required."


@dataclass
class AuthContext:
    session: AuthSession
    user: User
    service: AuthSessionService


def get_auth_settings(request: Request) -> ApplicationSettings:
    settings = request.app.state.settings
    if settings.installation.mode is not DeploymentMode.HOSTED:
        raise HTTPException(status_code=404, detail="Not found.")
    return settings


def session_service(
    db: Session,
    settings: ApplicationSettings,
) -> AuthSessionService:
    return AuthSessionService(
        db,
        idle_lifetime_minutes=(
            settings.security.session_lifetime_minutes
        ),
        absolute_lifetime_minutes=(
            settings.security.session_absolute_lifetime_minutes
        ),
    )


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def user_read(user: User) -> AuthUserRead:
    return AuthUserRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status,
        system_role=user.system_role,
    )


def require_auth_context(
    request: Request,
    settings: ApplicationSettings = Depends(get_auth_settings),
    db: Session = Depends(get_session),
) -> AuthContext:
    service = session_service(db, settings)
    resolved = service.resolve(
        request.cookies.get(settings.security.cookie_name),
        client_ip=client_ip(request),
    )
    if resolved is None:
        db.commit()
        raise HTTPException(
            status_code=401,
            detail=AUTHENTICATION_REQUIRED,
        )
    session, user = resolved
    return AuthContext(session=session, user=user, service=service)


def require_csrf_context(
    context: AuthContext = Depends(require_auth_context),
    csrf_token: str | None = Header(
        default=None,
        alias="X-CSRF-Token",
    ),
) -> AuthContext:
    if not context.service.validate_csrf(
        context.session,
        csrf_token,
    ):
        raise HTTPException(status_code=403, detail=CSRF_REQUIRED)
    return context


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
        user=user_read(user),
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
        user=user_read(context.user),
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
