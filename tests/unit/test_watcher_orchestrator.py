"""Tests for the EF-01 watcher orchestrator."""

# Coverage: EF-01, EF-06, INF-02

from datetime import datetime, timezone

import pytest

from backend.app.domain.ef01_capture.idempotency import EntryFingerprintReader
from backend.app.domain.ef01_capture.watch_folders import (
    WATCH_SUBDIRECTORIES,
    ensure_watch_root_layout,
)
from backend.app.domain.ef01_capture.watcher import (
    WatchProfile,
    WatcherOrchestrator,
    build_default_watch_profiles,
)
from backend.app.domain.ef06_entrystore.models import Entry

pytestmark = [pytest.mark.ef01, pytest.mark.ef06, pytest.mark.inf02]


class FakeEntryFingerprintReader(EntryFingerprintReader):
    def __init__(self, result):
        self.result = result
        self.queries = []

    def find_by_fingerprint(self, fingerprint: str, source_channel: str):  # noqa: D401
        self.queries.append((fingerprint, source_channel))
        return self.result


class FakeEntryCreator:
    def __init__(self):
        self.calls = []
        self.status_updates = []
        self.counter = 0

    def create_entry(
        self,
        *,
        source_type: str,
        source_channel: str,
        source_path: str,
        metadata,
        pipeline_status: str,
    ):  # noqa: D401
        self.counter += 1
        record = Entry.new(
            entry_id=f"entry-{self.counter}",
            timestamp=datetime.now(timezone.utc),
            metadata=metadata,
            pipeline_status=pipeline_status,
            source_type=source_type,
            source_channel=source_channel,
            source_path=source_path,
        )
        self.calls.append(
            {
                "source_type": source_type,
                "source_channel": source_channel,
                "source_path": source_path,
                "metadata": metadata,
                "pipeline_status": pipeline_status,
                "record": record,
            }
        )
        return record

    def update_pipeline_status(self, entry_id: str, *, pipeline_status: str):  # noqa: D401
        for call in self.calls:
            if call["record"].entry_id == entry_id:
                updated = call["record"].with_pipeline_status(
                    pipeline_status, timestamp=datetime.now(timezone.utc)
                )
                call["record"] = updated
                self.status_updates.append(
                    {"entry_id": entry_id, "pipeline_status": pipeline_status}
                )
                return updated
        raise KeyError(entry_id)


class FakeJobEnqueuer:
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


def _make_profile(root, job_type):
    if job_type == "transcription":
        return WatchProfile(
            root=root,
            source_type="audio",
            source_channel="watch_folder_audio",
            job_type=job_type,
        )
    return WatchProfile(
        root=root,
        source_type="document",
        source_channel="watch_folder_document",
        job_type=job_type,
    )


def test_watcher_orchestrator_processes_audio_file(tmp_path):
    root = tmp_path / "audio"
    profile = _make_profile(root, "transcription")
    ensure_watch_root_layout(root)
    incoming_file = root / WATCH_SUBDIRECTORIES[0] / "clip.wav"
    incoming_file.write_bytes(b"hello")

    reader = FakeEntryFingerprintReader(result=None)
    creator = FakeEntryCreator()
    jobs = FakeJobEnqueuer()

    orchestrator = WatcherOrchestrator([profile], reader, creator, jobs)
    orchestrator.run_once()

    processing_file = root / WATCH_SUBDIRECTORIES[1] / "clip.wav"
    assert processing_file.exists()
    assert not incoming_file.exists()

    assert creator.calls and creator.calls[0]["source_type"] == "audio"
    assert creator.calls[0]["source_channel"] == "watch_folder_audio"
    assert creator.calls[0]["source_path"] == str(processing_file)
    assert set(creator.calls[0]["metadata"]) == {
        "capture_fingerprint",
        "fingerprint_algo",
    }
    assert creator.calls[0]["pipeline_status"] == "captured"

    assert jobs.calls == [
        {
            "job_type": "transcription",
            "entry_id": "entry-1",
            "source_path": str(processing_file),
        }
    ]
    assert creator.status_updates == [
        {"entry_id": "entry-1", "pipeline_status": "queued_for_transcription"}
    ]


def test_watcher_orchestrator_skips_duplicates(tmp_path):
    root = tmp_path / "audio"
    profile = _make_profile(root, "transcription")
    ensure_watch_root_layout(root)
    incoming_file = root / WATCH_SUBDIRECTORIES[0] / "clip.wav"
    incoming_file.write_bytes(b"hello")

    reader = FakeEntryFingerprintReader(
        result=Entry.new(
            entry_id="existing",
            pipeline_status="queued_for_transcription",
            metadata={"capture_fingerprint": "abc"},
            source_type="audio",
            source_channel="watch_folder_audio",
        )
    )
    creator = FakeEntryCreator()
    jobs = FakeJobEnqueuer()

    orchestrator = WatcherOrchestrator([profile], reader, creator, jobs)
    orchestrator.run_once()

    # File should remain in incoming since we skipped the duplicate.
    assert incoming_file.exists()
    assert not creator.calls
    assert not jobs.calls


def test_build_default_watch_profiles_infers_audio_vs_documents(tmp_path):
    audio_root = tmp_path / "MyAudio"
    doc_root = tmp_path / "Docs"

    profiles = build_default_watch_profiles([audio_root, doc_root])

    assert profiles[0].job_type == "transcription"
    assert profiles[0].source_type == "audio"
    assert profiles[1].job_type == "doc_extraction"
    assert profiles[1].source_channel == "watch_folder_document"
