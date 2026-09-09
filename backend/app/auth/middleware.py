from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlmodel import Session

from app.auth.dependencies import (
    AUTHENTICATION_REQUIRED,
    CSRF_REQUIRED,
    client_ip,
    session_service,
)
from app.config import ApplicationSettings, DeploymentMode
from app.database import get_engine


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def authorize_hosted_api_request(
    request: Request,
    settings: ApplicationSettings,
) -> Response | None:
    with Session(get_engine()) as db:
        service = session_service(db, settings)
        resolved = service.resolve(
            request.cookies.get(settings.security.cookie_name),
            client_ip=client_ip(request),
        )
        if resolved is None:
            db.commit()
            return JSONResponse(
                status_code=401,
                content={"detail": AUTHENTICATION_REQUIRED},
            )
        auth_session, user = resolved
        if (
            request.method not in SAFE_METHODS
            and not service.validate_csrf(
                auth_session,
                request.headers.get("X-CSRF-Token"),
            )
        ):
            db.commit()
            return JSONResponse(
                status_code=403,
                content={"detail": CSRF_REQUIRED},
            )
        request.state.current_user_id = user.id
        db.commit()
    return None


def install_authentication_middleware(
    application: FastAPI,
    settings: ApplicationSettings,
) -> None:
    if settings.installation.mode is not DeploymentMode.HOSTED:
        return

    @application.middleware("http")
    async def protect_hosted_api(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or not (path == "/api" or path.startswith("/api/"))
            or path == "/api/auth"
            or path.startswith("/api/auth/")
        ):
            return await call_next(request)

        rejection = authorize_hosted_api_request(request, settings)
        if rejection is not None:
            return rejection
        return await call_next(request)
