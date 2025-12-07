"""System health endpoints for frontend polling."""

from fastapi import APIRouter, Depends

from ...config import Settings, load_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/healthz")
def healthcheck(settings: Settings = Depends(load_settings)) -> dict[str, str]:
    """Return coarse-grained backend readiness information."""

    return {
        "status": "ok",
        "environment": settings.environment,
        "entryStore": "pending",
        "jobQueue": "pending",
    }
