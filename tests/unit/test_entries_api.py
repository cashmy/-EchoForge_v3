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


def _seed_entry(
    gateway: InMemoryEntryStoreGateway,
    *,
    fingerprint: str,
    title: str,
    summary: str,
    type_id: str | None = None,
    type_label: str | None = None,
    domain_id: str | None = None,
    domain_label: str | None = None,
    pipeline_status: str | None = None,
    source_channel: str = "manual_text",
) -> str:
    entry = gateway.create_entry(
        source_type="document",
        source_channel=source_channel,
        metadata={
            "capture_fingerprint": fingerprint,
            "fingerprint_algo": "sha256",
        },
    )
    gateway.save_summary(
        entry.entry_id,
        summary=summary,
        display_title=title,
        semantic_tags=[title.lower()],
    )
    if pipeline_status and pipeline_status != entry.pipeline_status:
        gateway.update_pipeline_status(entry.entry_id, pipeline_status=pipeline_status)
    if any([type_id, type_label, domain_id, domain_label]):
        gateway.update_entry_taxonomy(
            entry.entry_id,
            type_id=type_id,
            type_label=type_label,
            domain_id=domain_id,
            domain_label=domain_label,
        )
    return entry.entry_id


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


def test_list_entries_returns_paginated_results(monkeypatch):
    monkeypatch.setenv("ENABLE_TAXONOMY_PATCH", "1")
    gateway = InMemoryEntryStoreGateway()
    first_id = _seed_entry(
        gateway,
        fingerprint="entry-a",
        title="Alpha Log",
        summary="Alpha summary",
        type_id="signal",
        type_label="Signal",
        domain_id="ops",
        domain_label="Ops",
        pipeline_status="queued_for_transcription",
    )
    second_id = _seed_entry(
        gateway,
        fingerprint="entry-b",
        title="Bravo Log",
        summary="Bravo summary",
        type_id="note",
        type_label="Note",
        domain_id="ops",
        domain_label="Ops",
    )
    client = _build_client(gateway)

    response = client.get("/api/entries", params={"page_size": 1, "page": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total_items"] == 2
    assert body["pagination"]["total_pages"] == 2
    assert body["items"][0]["entry_id"] == second_id

    second_page = client.get("/api/entries", params={"page_size": 1, "page": 2})
    assert second_page.json()["items"][0]["entry_id"] == first_id


def test_list_entries_filters_by_type_and_pipeline_status():
    gateway = InMemoryEntryStoreGateway()
    _seed_entry(
        gateway,
        fingerprint="entry-c",
        title="Signal Entry",
        summary="Semantics queued",
        type_id="signal",
        type_label="Signal",
        domain_id="ops",
        domain_label="Ops",
        pipeline_status="queued_for_transcription",
    )
    _seed_entry(
        gateway,
        fingerprint="entry-d",
        title="Note Entry",
        summary="Other pipeline",
        type_id="note",
        type_label="Note",
        domain_id="ops",
        domain_label="Ops",
    )
    client = _build_client(gateway)

    response = client.get(
        "/api/entries",
        params={
            "type_id": "signal",
            "pipeline_status": "queued_for_transcription",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["type_id"] == "signal"


def test_list_entries_supports_free_text_search():
    gateway = InMemoryEntryStoreGateway()
    target_id = _seed_entry(
        gateway,
        fingerprint="entry-e",
        title="Foxtrot Dossier",
        summary="This contains foxtrot intel",
        type_id="signal",
        type_label="Signal",
        domain_id="intel",
        domain_label="Intel",
    )
    _seed_entry(
        gateway,
        fingerprint="entry-f",
        title="Golf Log",
        summary="Generic text",
        type_id="note",
        type_label="Note",
        domain_id="ops",
        domain_label="Ops",
    )
    client = _build_client(gateway)

    response = client.get("/api/entries", params={"q": "Foxtrot"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["entry_id"] == target_id


def test_list_entries_rejects_invalid_pipeline_status():
    gateway = InMemoryEntryStoreGateway()
    client = _build_client(gateway)

    response = client.get("/api/entries", params={"pipeline_status": "not_real"})

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "EF07-INVALID-REQUEST"


def test_list_entries_validates_date_range():
    gateway = InMemoryEntryStoreGateway()
    client = _build_client(gateway)

    response = client.get(
        "/api/entries",
        params={
            "created_from": "2025-12-11T00:00:00Z",
            "created_to": "2025-12-10T00:00:00Z",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "EF07-INVALID-REQUEST"


def test_get_entry_detail_returns_single_entry(monkeypatch):
    monkeypatch.setenv("ENABLE_TAXONOMY_PATCH", "1")
    gateway = InMemoryEntryStoreGateway()
    entry_id = _seed_entry(
        gateway,
        fingerprint="entry-detail",
        title="Detail Entry",
        summary="Detail summary",
        type_id="note",
        type_label="Note",
        domain_id="ops",
        domain_label="Ops",
        pipeline_status="queued_for_transcription",
        source_channel="watch_folder_document",
    )
    client = _build_client(gateway)

    response = client.get(f"/api/entries/{entry_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["entry_id"] == entry_id
    assert body["summary"] == "Detail summary"
    assert body["pipeline_status"] == "queued_for_transcription"
    assert body["source_channel"] == "watch_folder_document"
    assert body["type_label"] == "Note"


def test_get_entry_detail_returns_404_for_missing_entry():
    gateway = InMemoryEntryStoreGateway()
    client = _build_client(gateway)

    response = client.get("/api/entries/not-real")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "EF07-NOT-FOUND"
