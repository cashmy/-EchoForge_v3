"""EF-07 capture endpoint placeholder."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/capture", tags=["capture"])


@router.post("")
def capture_entry() -> dict[str, str]:
    return {"status": "accepted"}
