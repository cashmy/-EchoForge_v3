"""EF-07 Entry endpoints placeholder."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/entries", tags=["entries"])


@router.get("")
def list_entries() -> list[dict[str, str]]:
    return []
