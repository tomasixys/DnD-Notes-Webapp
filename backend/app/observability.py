from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.responses import Response


logger = logging.getLogger("dnd_notes.requests")


@dataclass(frozen=True)
class MetricsSnapshot:
    requests_total: int
    errors_total: int
    requests_in_flight: int
    duration_seconds_total: float


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._requests_in_flight = 0
        self._duration_seconds_total = 0.0

    def begin(self) -> None:
        with self._lock:
            self._requests_in_flight += 1

    def finish(self, status_code: int, duration_seconds: float) -> None:
        with self._lock:
            self._requests_in_flight -= 1
            self._requests_total += 1
            if status_code >= 500:
                self._errors_total += 1
            self._duration_seconds_total += duration_seconds

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(
                requests_total=self._requests_total,
                errors_total=self._errors_total,
                requests_in_flight=self._requests_in_flight,
                duration_seconds_total=self._duration_seconds_total,
            )


def _request_log(
    request: Request,
    *,
    request_id: str,
    status_code: int,
    duration_seconds: float,
) -> str:
    return json.dumps(
        {
            "event": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(duration_seconds * 1000, 2),
            "client": (
                request.client.host
                if request.client is not None
                else None
            ),
        },
        separators=(",", ":"),
    )


def install_observability(application: FastAPI) -> RequestMetrics:
    metrics = RequestMetrics()
    application.state.request_metrics = metrics

    @application.middleware("http")
    async def observe_request(request: Request, call_next) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        started_at = perf_counter()
        status_code = 500
        metrics.begin()
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            duration = perf_counter() - started_at
            logger.exception(
                _request_log(
                    request,
                    request_id=request_id,
                    status_code=status_code,
                    duration_seconds=duration,
                )
            )
            raise
        finally:
            duration = perf_counter() - started_at
            metrics.finish(status_code, duration)
            if status_code < 500:
                logger.info(
                    _request_log(
                        request,
                        request_id=request_id,
                        status_code=status_code,
                        duration_seconds=duration,
                    )
                )

    return metrics
