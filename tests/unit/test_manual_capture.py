"""Tests for EF-01 manual text capture helpers."""

import pytest

from backend.app.domain.ef01_capture.manual import capture_manual_text
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway


def test_capture_manual_text_persists_entry_with_metadata():
    gateway = InMemoryEntryStoreGateway()

    entry = capture_manual_text(
        text="Manual note", entry_gateway=gateway, metadata={"title": "note"}
    )

    assert entry.source_type == "text"
    assert entry.pipeline_status == "captured"
    assert entry.metadata["manual_text_body"] == "Manual note"
    assert entry.metadata["manual_text_length"] == len("Manual note")
    assert entry.metadata["capture_fingerprint"]
    assert entry.metadata["fingerprint_algo"] == "sha256(text)"


def test_capture_manual_text_rejects_blank_payload():
    gateway = InMemoryEntryStoreGateway()

    with pytest.raises(ValueError):
        capture_manual_text(text="   ", entry_gateway=gateway)
