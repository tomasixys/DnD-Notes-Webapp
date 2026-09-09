from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect, select, update


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def claim_revision(
    db,
    resource: Any,
    expected_revision: int | object,
    *,
    resource_type: str,
) -> int:
    """Atomically advance one aggregate revision or raise a 409 conflict."""
    # FastAPI parameter defaults are marker objects when route functions are
    # invoked directly in unit tests. HTTP requests always provide an int, while
    # direct calls retain the resource's current revision.
    if not isinstance(expected_revision, int):
        expected_revision = resource.revision

    model = type(resource)
    mapper = sa_inspect(model)
    primary_key = mapper.primary_key
    identity = tuple(
        getattr(resource, column.key)
        for column in primary_key
    )
    conditions = [
        column == value
        for column, value in zip(primary_key, identity)
    ]
    next_revision = expected_revision + 1
    changed_at = utc_now()
    statement = (
        update(model)
        .where(
            *conditions,
            model.revision == expected_revision,
        )
        .values(
            revision=next_revision,
            updated_at=changed_at,
        )
        .execution_options(synchronize_session=False)
    )
    result = db.execute(statement)
    if result.rowcount != 1:
        current_revision = db.execute(
            select(model.revision).where(*conditions)
        ).scalar_one_or_none()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "revision_conflict",
                "resource_type": resource_type,
                "resource_id": (
                    identity[0] if len(identity) == 1 else list(identity)
                ),
                "expected_revision": expected_revision,
                "current_revision": current_revision,
                "message": (
                    "This resource changed after it was loaded. "
                    "Reload the current version before saving again."
                ),
            },
        )

    resource.revision = next_revision
    resource.updated_at = changed_at
    return next_revision
