from fastapi import FastAPI
from fastapi.routing import APIRoute


def _dependency_calls(dependant) -> set[object]:
    calls = {dependant.call}
    for child in dependant.dependencies:
        calls.update(_dependency_calls(child))
    return calls


def audit_campaign_route_authorization(application: FastAPI) -> None:
    """Fail startup when an application API route lacks an auth policy."""
    missing: list[str] = []
    for route in application.routes:
        if not isinstance(route, APIRoute):
            continue
        if (
            not route.path.startswith("/api/")
            or route.path.startswith("/api/auth/")
        ):
            continue
        calls = _dependency_calls(route.dependant)
        if not any(
            hasattr(call, "__campaign_authorization__")
            or hasattr(call, "__api_authentication__")
            for call in calls
        ):
            methods = ",".join(sorted(route.methods or ()))
            missing.append(f"{methods} {route.path}")
    if missing:
        raise RuntimeError(
            "API routes missing authentication/authorization "
            "classification: "
            + "; ".join(missing)
        )
