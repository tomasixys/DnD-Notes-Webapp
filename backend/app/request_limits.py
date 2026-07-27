from __future__ import annotations

import math
import re
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.auth.dependencies import client_ip
from app.config import (
    ApplicationSettings,
    DeploymentMode,
    RequestLimitSettings,
)


WINDOW_SECONDS = 60.0
SEARCH_PATH = re.compile(r"^/api/campaigns/\d+/search$")
EXPORT_PATH = re.compile(
    r"^/api/(?:admin/)?campaigns/\d+/backup/export$"
)
CHARACTER_IMAGE_PATH = re.compile(
    r"^/api/campaigns/\d+/characters/\d+/image$"
)
CAMPAIGN_PATH = re.compile(r"^/api/campaigns(?:/\d+)?$")


@dataclass
class RateLimitBucket:
    started_at: float
    count: int = 0


class FixedWindowRateLimiter:
    """Small-process limiter for the supported single-app hosted stack."""

    def __init__(
        self,
        *,
        window_seconds: float = WINDOW_SECONDS,
        clock: Callable[[], float] | None = None,
    ):
        self.window_seconds = window_seconds
        self.clock = clock or time.monotonic
        self._buckets: dict[tuple[str, str], RateLimitBucket] = {}
        self._lock = threading.Lock()

    def consume(
        self,
        category: str,
        source: str,
        limit: int,
    ) -> tuple[bool, int]:
        now = self.clock()
        key = category, source
        with self._lock:
            bucket = self._buckets.get(key)
            if (
                bucket is None
                or now - bucket.started_at >= self.window_seconds
            ):
                bucket = RateLimitBucket(started_at=now)
                self._buckets[key] = bucket
            if bucket.count >= limit:
                retry_after = max(
                    1,
                    math.ceil(
                        self.window_seconds - (now - bucket.started_at)
                    ),
                )
                return False, retry_after
            bucket.count += 1
            self._remove_expired(now)
            return True, 0

    def _remove_expired(self, now: float) -> None:
        if len(self._buckets) < 1000:
            return
        expired = [
            key
            for key, bucket in self._buckets.items()
            if now - bucket.started_at >= self.window_seconds
        ]
        for key in expired:
            self._buckets.pop(key, None)


def classify_limited_request(
    request: Request,
    settings: RequestLimitSettings,
) -> tuple[str, int] | None:
    method = request.method.upper()
    path = request.url.path
    if method == "POST" and SEARCH_PATH.fullmatch(path):
        return "search", settings.search_per_minute
    if method == "POST" and path == "/api/campaigns/backup/import":
        return "import", settings.import_per_minute
    if method == "GET" and EXPORT_PATH.fullmatch(path):
        return "export", settings.export_per_minute
    if (
        method in {"POST", "PUT"}
        and request.headers.get("content-type", "").lower().startswith(
            "multipart/form-data"
        )
        and (
            CAMPAIGN_PATH.fullmatch(path)
            or CHARACTER_IMAGE_PATH.fullmatch(path)
        )
    ):
        return "upload", settings.upload_per_minute
    return None


def install_request_limits(
    application: FastAPI,
    settings: ApplicationSettings,
) -> None:
    limits = settings.request_limits
    if (
        settings.installation.mode is not DeploymentMode.HOSTED
        or not limits.enabled
    ):
        return
    limiter = FixedWindowRateLimiter()
    application.state.request_limiter = limiter

    @application.middleware("http")
    async def apply_request_limits(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        classification = classify_limited_request(request, limits)
        if classification is None:
            return await call_next(request)
        category, limit = classification
        allowed, retry_after = limiter.consume(
            category,
            client_ip(request),
            limit,
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Too many {category} requests. Try again later."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
