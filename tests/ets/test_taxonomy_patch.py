"""ETS scenarios for taxonomy patch workflows."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_entry_gateway
from backend.app.api.routers import entries
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway

pytestmark = [pytest.mark.ets_taxonomy, pytest.mark.ef06, pytest.mark.ef07]


def _build_client(gateway: InMemoryEntryStoreGateway) -> TestClient:
    app = FastAPI()
    app.include_router(entries.router)
    app.dependency_overrides[get_entry_gateway] = lambda: gateway
    return TestClient(app)


def test_taxonomy_patch_updates_entry_and_records_event(monkeypatch):
    monkeypatch.setenv("ENABLE_TAXONOMY_PATCH", "1")
    gateway = InMemoryEntryStoreGateway()
    entry = gateway.create_entry(
        source_type="document",
        source_channel="manual_text",
        source_path="/tmp/ets-doc.txt",
        metadata={"capture_fingerprint": "ets-tax", "fingerprint_algo": "sha256"},
    )
    client = _build_client(gateway)

    resp = client.patch(
        f"/api/entries/{entry.entry_id}",
        json={
            "taxonomy": {
                "type": {"id": "architecture_note", "label": "Architecture Note"},
                "domain": {"label": "Platform"},
            }
        },
        headers={"X-Actor-Id": "ets", "X-Actor-Source": "suite"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["taxonomy"]["type"]["id"] == "architecture_note"
    assert body["taxonomy"]["domain"]["pending_reconciliation"] is True

    snapshot = gateway.get_entry(entry.entry_id)
    events = snapshot.metadata.get("capture_events") or []
    assert events[-1]["type"] == "taxonomy.reference.updated"
    assert events[-1]["data"]["dimension"] == "domain"


def test_taxonomy_patch_clear_emits_cleared_event(monkeypatch):
    monkeypatch.setenv("ENABLE_TAXONOMY_PATCH", "1")
    gateway = InMemoryEntryStoreGateway()
    entry = gateway.create_entry(
        source_type="document",
        source_channel="manual_text",
        source_path="/tmp/ets-doc-clear.txt",
        metadata={"capture_fingerprint": "ets-tax-clear", "fingerprint_algo": "sha256"},
    )
    gateway.update_entry_taxonomy(
        entry.entry_id,
        type_id="legacy_type",
        type_label="Legacy Type",
        domain_id=None,
        domain_label=None,
    )
    client = _build_client(gateway)

    resp = client.patch(
        f"/api/entries/{entry.entry_id}",
        json={"taxonomy": {"type": {"clear": True}}},
        headers={"X-Actor-Id": "ets", "X-Actor-Source": "suite"},
    )

    assert resp.status_code == 200
    snapshot = gateway.get_entry(entry.entry_id)
    assert snapshot.type_id is None and snapshot.type_label is None
    events = snapshot.metadata.get("capture_events") or []
    assert events[-1]["type"] == "taxonomy.reference.cleared"
    assert events[-1]["data"]["dimension"] == "type"


def test_taxonomy_patch_rejects_when_feature_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_TAXONOMY_PATCH", raising=False)
    gateway = InMemoryEntryStoreGateway()
    entry = gateway.create_entry(
        source_type="document",
        source_channel="manual_text",
        source_path="/tmp/ets-doc-disabled.txt",
        metadata={
            "capture_fingerprint": "ets-tax-disabled",
            "fingerprint_algo": "sha256",
        },
    )
    client = _build_client(gateway)

    resp = client.patch(
        f"/api/entries/{entry.entry_id}",
        json={"taxonomy": {"type": {"label": "Architecture Note"}}},
    )

    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error_code"] == "EF07-FEATURE-DISABLED"
