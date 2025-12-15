"""Manual text capture helpers for EF-01."""

from __future__ import annotations

from hashlib import sha256
from typing import Dict, Optional

from ..ef06_entrystore.gateway import Entry, EntryStoreGateway
from ...infra.logging import get_logger

MANUAL_TEXT_BODY_KEY = "manual_text_body"
MANUAL_TEXT_LENGTH_KEY = "manual_text_length"
MANUAL_TEXT_FINGERPRINT_ALGO = "sha256(text)"

__all__ = ["capture_manual_text"]

logger = get_logger(__name__)


def capture_manual_text(
    *,
    text: str,
    entry_gateway: EntryStoreGateway,
    source_channel: str = "manual_text",
    metadata: Optional[Dict[str, object]] = None,
    display_title: Optional[str] = None,
) -> Entry:
    """Persist a manual text capture via EF-06 EntryStore."""

    normalized = (text or "").strip()
    if not normalized:
        logger.warning("manual_text_capture_rejected_empty")
        raise ValueError("text must not be empty")

    fingerprint = sha256(normalized.encode("utf-8")).hexdigest()
    merged_metadata: Dict[str, object] = dict(metadata or {})
    merged_metadata.setdefault("capture_fingerprint", fingerprint)
    merged_metadata.setdefault("fingerprint_algo", MANUAL_TEXT_FINGERPRINT_ALGO)
    merged_metadata[MANUAL_TEXT_BODY_KEY] = normalized
    merged_metadata[MANUAL_TEXT_LENGTH_KEY] = len(normalized)

    if display_title is None:
        raw_title = merged_metadata.get("manual_entry_title")
        if isinstance(raw_title, str):
            trimmed_title = raw_title.strip()
            display_title = trimmed_title or None

    entry = entry_gateway.create_entry(
        source_type="text",
        source_channel=source_channel,
        metadata=merged_metadata,
        pipeline_status="captured",
        display_title=display_title,
    )
    logger.info(
        "manual_text_capture_created",
        extra={
            "entry_id": entry.entry_id,
            "source_channel": source_channel,
            "text_length": len(normalized),
        },
    )
    return entry
