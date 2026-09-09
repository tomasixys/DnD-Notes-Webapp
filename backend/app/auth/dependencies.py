from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlmodel import Session, select

from app.auth.models import AuthSession, User
from app.auth.administration import LOCAL_USER_USERNAME
from app.auth.sessions import AuthSessionService
from app.config import ApplicationSettings, DeploymentMode
from app.database import get_session


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


def get_application_settings(request: Request) -> ApplicationSettings:
    return request.app.state.settings


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


def get_current_user(
    request: Request,
    settings: ApplicationSettings = Depends(get_application_settings),
    db: Session = Depends(get_session),
) -> User | None:
    if settings.installation.mode is DeploymentMode.LOCAL:
        return db.exec(
            select(User).where(
                User.normalized_username == LOCAL_USER_USERNAME
            )
        ).first()

    service = session_service(db, settings)
    resolved = service.resolve(
        request.cookies.get(settings.security.cookie_name),
        client_ip=client_ip(request),
    )
    db.commit()
    return resolved[1] if resolved is not None else None


def require_current_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=401,
            detail=AUTHENTICATION_REQUIRED,
        )
    return user


require_current_user.__api_authentication__ = True


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
