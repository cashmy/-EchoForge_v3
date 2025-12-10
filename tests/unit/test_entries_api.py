"""FastAPI tests for entry taxonomy patch endpoint."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_entry_gateway
from backend.app.api.routers import entries
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway

pytestmark = [pytest.mark.ef07, pytest.mark.ef06]


def _build_client(gateway: InMemoryEntryStoreGateway) -> TestClient:
    app = FastAPI()
    app.include_router(entries.router)
    app.dependency_overrides[get_entry_gateway] = lambda: gateway
    return TestClient(app)


def test_patch_entry_taxonomy_updates_ids_and_labels(monkeypatch):
    monkeypatch.setenv("ENABLE_TAXONOMY_PATCH", "1")
    gateway = InMemoryEntryStoreGateway()
    entry = gateway.create_entry(
        source_type="document",
        source_channel="manual_text",
        source_path="/tmp/doc.txt",
        metadata={"capture_fingerprint": "entry-tax", "fingerprint_algo": "sha256"},
    )
    client = _build_client(gateway)

    response = client.patch(
        f"/api/entries/{entry.entry_id}",
        json={
            "taxonomy": {
                "type": {"id": "project_note", "label": "Project Note"},
                "domain": {"label": "Product Ops"},
            }
        },
        headers={"X-Actor-Id": "tester", "X-Actor-Source": "unit"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["taxonomy"]["type"]["id"] == "project_note"
    assert body["taxonomy"]["domain"]["pending_reconciliation"] is True
    stored = gateway.get_entry(entry.entry_id)
    assert stored.type_id == "project_note"
    assert stored.domain_label == "Product Ops"


def test_patch_entry_taxonomy_clear_dimension(monkeypatch):
    monkeypatch.setenv("ENABLE_TAXONOMY_PATCH", "1")
    gateway = InMemoryEntryStoreGateway()
    entry = gateway.create_entry(
        source_type="document",
        source_channel="manual_text",
        source_path="/tmp/doc2.txt",
        metadata={
            "capture_fingerprint": "entry-tax-clear",
            "fingerprint_algo": "sha256",
        },
    )
    gateway.update_entry_taxonomy(
        entry.entry_id,
        type_id="project_note",
        type_label="Project Note",
        domain_id="product_ops",
        domain_label="Product Ops",
    )
    client = _build_client(gateway)

    response = client.patch(
        f"/api/entries/{entry.entry_id}",
        json={"taxonomy": {"type": {"clear": True}}},
    )

    assert response.status_code == 200
    assert response.json()["taxonomy"]["type"]["id"] is None
    stored = gateway.get_entry(entry.entry_id)
    assert stored.type_id is None
    assert stored.type_label is None


def test_patch_entry_taxonomy_rejects_when_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_TAXONOMY_PATCH", raising=False)
    gateway = InMemoryEntryStoreGateway()
    entry = gateway.create_entry(
        source_type="document",
        source_channel="manual_text",
        source_path="/tmp/doc3.txt",
        metadata={
            "capture_fingerprint": "entry-tax-disabled",
            "fingerprint_algo": "sha256",
        },
    )
    client = _build_client(gateway)

    response = client.patch(
        f"/api/entries/{entry.entry_id}",
        json={"taxonomy": {"type": {"id": "project_note", "label": "Project Note"}}},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "EF07-FEATURE-DISABLED"
