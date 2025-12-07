# EF-02 Capture Events & File Rollover Guide

_Last updated: 2025-12-07 — GPT-5.1-Codex_

## Purpose

EF-02 transcription runs now emit structured `metadata.capture_events[]` entries on every Entry record and physically move media files between the EF-01 watch-folder stages. This guide documents what operators and developers should expect, so downstream tooling (dashboards, ETS scripts, runtime monitors) can reason about the audit trail.

## Event Timeline

| Event Type | When It Fires | Metadata Keys | Notes |
| --- | --- | --- | --- |
| `transcription_started` | Immediately after EF-02 pulls a job and flips the entry to `transcription_in_progress`. | `stage`, `pipeline_status`, `source_channel`, `correlation_id?`, `source_path`. | Serves as the handshake that the worker accepted the payload. Use it to correlate with INF-02 dequeues. |
| `transcription_completed` | After INF-04 returns a transcript and EF-06 is updated with text/segments/metadata. | Includes `processing_ms`, `segment_count`, plus base keys. | Signals success before downstream EF-04 enqueue occurs. |
| `transcription_failed` | Whenever the worker encounters a non-recoverable error (or exhausts retries) and records `transcription_error`. | Adds `error_code`, `retryable`, `processing_ms`. | Fired even if the exception is re-raised to INF-02; check `retryable` to know whether a re-enqueue occurred. |
| `transcription_file_rolled` | After the worker moves media from `processing/` into `processed/` or `failed/`. | Adds `destination_path`, `target_stage`. | Emitted for both success (`processed`) and failure (`failed`) so file lifecycle is auditable. |

All events share:

- `stage="transcription"`
- `pipeline_status` reflecting the EF-06 state at the time of emission
- `source_channel` mirroring the original EF-01 ingress channel
- Optional `correlation_id` (propagated from EF-01 / INF-02 payloads)

## File Rollover Semantics

The worker expects EF-01 files to reside under `<watch_root>/processing/`. After completion it moves the file into:

- `processed/` on success
- `failed/` on terminal failure

If a file is missing (already cleaned up) the event is skipped. When a destination already exists (e.g., duplicate file name), the worker overwrites the prior file to keep the latest artifact.

## Sample Metadata Snippet

```json
{
  "capture_fingerprint": "fp-123",
  "fingerprint_algo": "sha256",
  "capture_events": [
    {
      "type": "transcription_started",
      "timestamp": "2025-12-07T16:05:01.223Z",
      "data": {
        "stage": "transcription",
        "pipeline_status": "transcription_in_progress",
        "source_channel": "watch_folder_audio",
        "source_path": "C:/watch/audio/processing/clip.wav",
        "correlation_id": "corr-001"
      }
    },
    {
      "type": "transcription_completed",
      "timestamp": "2025-12-07T16:05:01.812Z",
      "data": {
        "stage": "transcription",
        "pipeline_status": "transcription_complete",
        "source_channel": "watch_folder_audio",
        "processing_ms": 589,
        "segment_count": 3,
        "correlation_id": "corr-001"
      }
    },
    {
      "type": "transcription_file_rolled",
      "timestamp": "2025-12-07T16:05:01.900Z",
      "data": {
        "stage": "transcription",
        "pipeline_status": "transcription_complete",
        "source_channel": "watch_folder_audio",
        "target_stage": "processed",
        "destination_path": "C:/watch/audio/processed/clip.wav"
      }
    }
  ]
}
```

## Operational Tips

1. **ETS Assertions** — Protocol runners can assert `capture_events` ordering to prove the pipeline executed each stage.
2. **Monitoring Hooks** — The `transcription_file_rolled` event provides the canonical destination path; watchers can safely delete the original `processing/` file after this fires.
3. **Future Stages** — EF-03/EF-04/EF-05 should follow the same event naming pattern (`<stage>_started`, `<stage>_completed`, `<stage>_failed`, `<stage>_file_rolled`) for uniform dashboards.
4. **Backfills** — When replaying jobs, ensure the `correlation_id` remains stable so event streams can stitch together rehyrdated entries.

## Next Steps

- Mirror this format for EF-03 and EF-04 once their workers emit events.
- Consider surfacing these events in the desktop dashboard to provide end users with human-readable timelines.
