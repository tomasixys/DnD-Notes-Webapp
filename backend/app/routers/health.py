from fastapi import APIRouter, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlmodel import Session

from app.database import get_engine
from app.observability import RequestMetrics


router = APIRouter(tags=["operations"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/health/live")
def liveness(response: Response) -> dict[str, str]:
    _no_store(response)
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(response: Response) -> dict[str, str]:
    _no_store(response)
    try:
        with Session(get_engine()) as db:
            db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ready"}


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(request: Request) -> PlainTextResponse:
    collector: RequestMetrics = request.app.state.request_metrics
    snapshot = collector.snapshot()
    body = "\n".join(
        (
            "# TYPE dnd_notes_http_requests_total counter",
            (
                "dnd_notes_http_requests_total "
                f"{snapshot.requests_total}"
            ),
            "# TYPE dnd_notes_http_errors_total counter",
            f"dnd_notes_http_errors_total {snapshot.errors_total}",
            "# TYPE dnd_notes_http_requests_in_flight gauge",
            (
                "dnd_notes_http_requests_in_flight "
                f"{snapshot.requests_in_flight}"
            ),
            "# TYPE dnd_notes_http_request_duration_seconds_total counter",
            (
                "dnd_notes_http_request_duration_seconds_total "
                f"{snapshot.duration_seconds_total:.6f}"
            ),
            "",
        )
    )
    return PlainTextResponse(
        content=body,
        media_type="text/plain; version=0.0.4",
        headers={"Cache-Control": "no-store"},
    )
