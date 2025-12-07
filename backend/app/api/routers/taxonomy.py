"""EF-07 taxonomy endpoints placeholder."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["taxonomy"])


@router.get("/types")
def list_types() -> list[dict[str, str]]:
    return []
