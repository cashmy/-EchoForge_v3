"""EF-06 EntryStore data models aligned with EF06 spec v1.1."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

__all__ = [
    "Entry",
    "utcnow",
]


def utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Entry:
    """Represents a stored Entry row shared across EF components."""

    entry_id: str
    source_type: str
    source_channel: str
    source_path: Optional[str]
    pipeline_status: str
    cognitive_status: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        *,
        source_type: str,
        source_channel: str,
        source_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        pipeline_status: str = "ingested",
        cognitive_status: str = "unreviewed",
        entry_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> "Entry":
        """Factory that applies EF-06 defaults and generates IDs/timestamps."""

        ts = timestamp or utcnow()
        meta = dict(metadata or {})
        return cls(
            entry_id=entry_id or str(uuid4()),
            source_type=source_type,
            source_channel=source_channel,
            source_path=source_path,
            pipeline_status=pipeline_status,
            cognitive_status=cognitive_status,
            metadata=meta,
            created_at=ts,
            updated_at=ts,
        )

    def with_pipeline_status(
        self, pipeline_status: str, *, timestamp: Optional[datetime] = None
    ) -> "Entry":
        """Return a copy with refreshed pipeline status and timestamp."""

        return replace(
            self,
            pipeline_status=pipeline_status,
            updated_at=timestamp or utcnow(),
        )
