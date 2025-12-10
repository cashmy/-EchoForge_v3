"""System health endpoints for frontend polling."""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from ...config import Settings, load_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/healthz")
def healthcheck(settings: Settings = Depends(load_settings)) -> dict[str, Any]:
    """Return coarse-grained backend readiness information."""

    feature_flags: Dict[str, Any] = settings.features or {}

    return {
        "status": "ok",
        "environment": settings.environment,
        "entryStore": "pending",
        "jobQueue": "pending",
        "featureFlags": feature_flags,
    }
