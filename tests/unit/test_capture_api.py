"""Tests for EF-07 /capture endpoint flows."""

import hashlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_entry_gateway, get_job_enqueuer
from backend.app.api.routers import capture
from backend.app.domain.ef01_capture.fingerprint import compute_file_fingerprint
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway


class RecordingJobAdapter:
    def __init__(self):
        self.calls = []

    def enqueue(self, job_type: str, *, entry_id: str, source_path: str):  # noqa: D401
        self.calls.append(
            {
                "job_type": job_type,
                "entry_id": entry_id,
                "source_path": source_path,
            }
        )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(capture.router)
    return app


def test_capture_text_mode_creates_entry():
    app = _build_app()
    gateway = InMemoryEntryStoreGateway()
    app.dependency_overrides[get_entry_gateway] = lambda: gateway
    app.dependency_overrides[get_job_enqueuer] = lambda: RecordingJobAdapter()
    client = TestClient(app)

    resp = client.post(
        "/api/capture",
        json={
            "mode": "text",
            "content": "Manual API note",
            "metadata": {"title": "note"},
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["ingest_state"] == "captured"
    fingerprint = hashlib.sha256("Manual API note".encode("utf-8")).hexdigest()
    entry = gateway.find_by_fingerprint(fingerprint, "manual_text")
    assert entry is not None

    app.dependency_overrides.clear()


def test_capture_file_ref_enqueues_job_and_updates_status(tmp_path):
    app = _build_app()
    gateway = InMemoryEntryStoreGateway()
    jobs = RecordingJobAdapter()
    app.dependency_overrides[get_entry_gateway] = lambda: gateway
    app.dependency_overrides[get_job_enqueuer] = lambda: jobs
    client = TestClient(app)

    file_path = tmp_path / "demo.wav"
    file_path.write_bytes(b"audio-bytes")

    resp = client.post(
        "/api/capture",
        json={
            "mode": "file_ref",
            "file_path": str(file_path),
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["ingest_state"] == "queued_for_transcription"
    assert jobs.calls and jobs.calls[0]["job_type"] == "transcription"

    fingerprint, _ = compute_file_fingerprint(file_path)
    entry = gateway.find_by_fingerprint(fingerprint, "api_ingest")
    assert entry is not None
    assert entry.pipeline_status == "queued_for_transcription"

    app.dependency_overrides.clear()


def test_capture_file_ref_detects_duplicates(tmp_path):
    app = _build_app()
    gateway = InMemoryEntryStoreGateway()
    jobs = RecordingJobAdapter()
    app.dependency_overrides[get_entry_gateway] = lambda: gateway
    app.dependency_overrides[get_job_enqueuer] = lambda: jobs
    client = TestClient(app)

    file_path = tmp_path / "demo.wav"
    file_path.write_bytes(b"audio-bytes")

    first = client.post(
        "/api/capture",
        json={"mode": "file_ref", "file_path": str(file_path)},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/capture",
        json={"mode": "file_ref", "file_path": str(file_path)},
    )

    assert duplicate.status_code == 409
    detail = duplicate.json()["detail"]
    assert detail["error_code"] == "EF07-CONFLICT"

    app.dependency_overrides.clear()
