# EchoForge Tests

- `e2e/`: cross-package runtime tests for Shapes A/B.
- `smoke_desktop/`: Electron smoke scenarios verifying EF-07.1 host adapter.

## Unit Suite Overview

Each `tests/unit/test_*.py` file focuses on a distinct piece of the EF-01/EF-06 ingestion path:

- `test_entrystore_gateway.py` — Verifies the in-memory EF-06 gateway enforces fingerprints, sets defaults, supports lookups by fingerprint, and updates pipeline statuses atomically.
- `test_fingerprint.py` — Ensures file fingerprinting produces deterministic hashes/algorithms across binary and text fixtures, catching regressions in idempotency inputs.
- `test_idempotency.py` — Exercises the decision matrix for EF-01 duplicates, confirming that queued/processing entries are skipped while failed ones trigger retries.
- `test_manual_capture.py` — Checks the manual text capture helper for fingerprint generation, metadata persistence, and validation of empty payloads.
- `test_capture_api.py` — Validates the `/api/capture` endpoint for both text and file-ref submissions, including INF-02 job enqueueing and duplicate detection.
- `test_config_loader.py` — Verifies INF-01 config profiles load correctly, honoring `ECHOFORGE_CONFIG_PROFILE`, capture watch roots, manual hashing recipes, and job-queue settings.
- `test_watch_folders.py` — Validates that watch roots are scaffolded with `incoming/processing/processed/failed` directories and that helper utilities guard against misconfiguration.
- `test_watcher_orchestrator.py` — Covers the orchestration loop: fingerprint lookup, file moves, entry creation defaults, job enqueue payloads, and duplicate short-circuiting.
- `test_watcher_runtime.py` — Runs the runtime adapter end-to-end for a temporary watch root, asserting that jobs are enqueued via the INF-02 shim and entries transition to queued statuses after processing.

## ETS Coverage (M01)

The following unit suites double as executable ETS-EF01 cases for Milestone 1:

- **Folder lifecycle (`incoming` → `processing`)** — `test_watch_folders.py`, `test_watcher_runtime.py`
- **Idempotency enforcement** — `test_idempotency.py`, duplicate scenario in `test_watcher_orchestrator.py`, `/api/capture` conflict test
- **Entry creation metadata** — `test_entrystore_gateway.py`, `test_manual_capture.py`, watcher orchestrator assertions
- **INF-02 job handoff** — `test_watcher_runtime.py` (watch roots) and `test_capture_api.py::test_capture_file_ref_enqueues_job`
- **/api/capture behavior (text + file_ref)** — `test_capture_api.py`

Run all ETS-aligned tests via:

```bash
$env:PYTHONPATH='d:\@EchoForge_v3'; pytest tests/unit
```
