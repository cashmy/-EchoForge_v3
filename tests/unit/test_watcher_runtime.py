"""Tests for EF-01 watcher runtime helpers."""

from backend.app.domain.ef01_capture.fingerprint import compute_file_fingerprint
from backend.app.domain.ef01_capture.runtime import InfraJobQueueAdapter, run_watch_once
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway


class RecordingJobAdapter(InfraJobQueueAdapter):
    def __init__(self):
        self.payloads = []
        super().__init__(enqueue_fn=self._record)

    def _record(self, job_type: str, payload: dict):
        self.payloads.append((job_type, payload))


def test_run_watch_once_processes_files_and_enqueues_jobs(tmp_path):
    audio_root = tmp_path / "audio"
    incoming_dir = audio_root / "incoming"
    incoming_dir.mkdir(parents=True)
    file_path = incoming_dir / "sample.wav"
    file_path.write_bytes(b"data")

    entry_gateway = InMemoryEntryStoreGateway()
    jobs = RecordingJobAdapter()

    run_watch_once([audio_root], entry_gateway=entry_gateway, job_enqueuer=jobs)

    processing_path = audio_root / "processing" / "sample.wav"
    assert processing_path.exists()
    assert len(jobs.payloads) == 1
    job_type, payload = jobs.payloads[0]
    assert job_type == "transcription"
    assert payload["source_path"] == str(processing_path)
    assert payload["entry_id"]

    fingerprint, _ = compute_file_fingerprint(processing_path)
    entry = entry_gateway.find_by_fingerprint(fingerprint, "watch_folder_audio")
    assert entry is not None
    assert entry.pipeline_status == "queued_for_transcription"
