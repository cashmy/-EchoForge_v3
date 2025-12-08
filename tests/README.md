# EchoForge Tests

## Directory Breakdown

- `tests/unit/` — Python suites covering every EF/INF component in the ingestion pipeline. Run these during day-to-day development and before closing a milestone task.
- `tests/e2e/` — Cross-package runtime tests for Runtime Shapes A/B. They exercise the Electron host, REST API, and local services together.
- `tests/smoke_desktop/` — Electron smoke scenarios that validate the EF-07 desktop host adapter wiring.

## Unit Suite Inventory

### Capture + EntryStore Foundations
- `test_fingerprint.py` — Deterministic hashing for binary/text fixtures to protect EF-01 idempotency inputs.
- `test_idempotency.py` — Duplicate decision matrix (skip queued/processing entries, retry failed ones).
- `test_manual_capture.py` — Manual text capture helper for fingerprints, metadata persistence, and empty-payload validation.
- `test_capture_api.py` — `/api/capture` text + file_ref submissions, INF-02 enqueueing, and duplicate detection responses.
- `test_entrystore_gateway.py` — In-memory EF-06 gateway defaults, fingerprint enforcement, lookups, and pipeline status transitions.
- `test_config_loader.py` — INF-01 profile loading, environment overrides, watch root hydration, and job queue defaults.
- `test_watch_folders.py` — Ensures watch roots contain the expected `incoming/processing/processed/failed` layout and guardrails.
- `test_watcher_orchestrator.py` — Full watcher loop (fingerprint lookup, file moves, entry creation, job enqueue payloads).
- `test_watcher_runtime.py` — Runtime adapter exercising temporary watch roots with INF-02 shim to confirm queue hand-offs.

### Pipeline Workers & Services
- `test_transcription_worker.py` (EF-02) — Success/failure paths for audio jobs, EF-06 persistence, downstream normalization enqueueing, and INF-04 retry semantics.
- `test_llm_gateway.py` (INF-04/EF-02/EF-05) — Whisper proxy wrappers plus semantic gateway JSON parsing, error translation, and stub fallbacks.
- `test_whisper_client.py` (INF-04) — faster-whisper adapter caches, availability gating, and decode/model option construction.
- `test_ef03_extraction_service.py` (EF-03) — File-type specific extraction helpers (`python-docx`, `pdfminer`) plus OCR-required error handling.
- `test_extraction_worker.py` (EF-03/INF-02) — Document worker verbatim output, segment caching, truncation, capture metadata, and normalization enqueueing.
- `test_normalization_worker.py` (EF-04/INF-02) — Text cleanup profiles, segment thresholds, override handling, and semantic job enqueueing.
- `test_semantic_worker.py` (EF-05/INF-04) — Prompt construction, structured tag/classification persistence, capture metadata, and retry/backoff handling for semantic enrichment.

## Spec Markers & Targeted Runs

Markers (from `pytest.ini`): `ef01`, `ef02`, `ef03`, `ef04`, `ef05`, `ef06`, `ef07`, `inf01`, `inf02`, `inf04`.

Examples:
- Capture + watcher focus: `pytest -m ef01 tests/unit`
- EntryStore + job queue surface: `pytest -m "ef06 and inf02" tests/unit`
- EF-02 through EF-05 pipeline sweep: `pytest -m "ef02 or ef03 or ef04 or ef05" tests/unit`
- LLM/Whisper integration only: `pytest -m inf04 tests/unit/test_llm_gateway.py tests/unit/test_whisper_client.py`

Use markers during milestone sign-off or while iterating on a specific subsystem to avoid running the entire suite.

## Local Watch Roots

`watch_roots/` is ignored in git because developers often stage large media files or mount external volumes during ETS runs. Before exercising EF-01 watchers locally, run:

```powershell
python scripts/setup_watch_roots.py
```

This script creates the default audio/document trees (each with `incoming`, `processing`, `processed`, and `failed`) plus helper directories such as `watch_roots/transcripts`. To relocate watch roots, first run the script, then update `capture.watch_roots[].root_path` in your INF-01 profile.

## ETS Coverage Checklists

### M01 (Capture/EntryStore)
- **Folder lifecycle (`incoming` → `processing`)** — `test_watch_folders.py`, `test_watcher_runtime.py`
- **Idempotency enforcement** — `test_idempotency.py`, duplicate scenario in `test_watcher_orchestrator.py`, `/api/capture` conflict cases
- **Entry creation metadata** — `test_entrystore_gateway.py`, `test_manual_capture.py`, watcher orchestrator assertions
- **INF-02 job handoff** — `test_watcher_runtime.py`, `test_capture_api.py::test_capture_file_ref_enqueues_job`
- **/api/capture behavior (text + file_ref)** — `test_capture_api.py`

### M02 (EF-02 → EF-05 pipeline)
- **Transcription + Whisper gateway** — `test_transcription_worker.py`, `test_llm_gateway.py`, `test_whisper_client.py`
- **Document extraction** — `test_ef03_extraction_service.py`, `test_extraction_worker.py`
- **Normalization** — `test_normalization_worker.py`
- **Semantic enrichment** — `test_semantic_worker.py`

Run all ETS-aligned unit tests via:

```powershell
$env:PYTHONPATH='d:\\@EchoForge_v3'; pytest tests/unit
```

## Whisper ETS Notes (M02-T02a)

Real-media validation uses the bundled WAV clips in `watch_roots/audio/incoming/` (`20250907115516.WAV`, `20250908132309.WAV`).

1. **Enable Whisper:** set `ECHOFORGE_WHISPER_ENABLED=1` (or adjust your YAML profile) and install `faster-whisper`. Override `ECHOFORGE_WHISPER_MODEL_ID`, `ECHOFORGE_WHISPER_DEVICE`, etc., to match your hardware.
2. **Smoke the unit suites:** `pytest -m "ef02 and inf04" tests/unit/test_llm_gateway.py tests/unit/test_transcription_worker.py tests/unit/test_whisper_client.py`.
3. **Stage audio:** copy a WAV from `watch_roots/audio/incoming` to `watch_roots/audio/processing` (the worker moves files from `processing/` → `processed/`).
4. **Invoke EF-02 manually:**
   ```powershell
   $env:PYTHONPATH='d:\\@EchoForge_v3'
   python - <<'PY'
   from backend.app.jobs import transcription_worker
   payload = {
       "entry_id": "ETS-demo-entry",
       "source_path": r"d:\\@EchoForge_v3\\watch_roots\\audio\\processing\\20250907115516.WAV",
       "source_channel": "watch_folder_audio",
       "fingerprint": "ets-demo-fp",
       "media_type": "audio/wav",
       "language_hint": "en",
       "llm_profile": "transcribe_v1",
       "correlation_id": "ets-whisper-001",
   }
   transcription_worker.handle(payload)
   PY
   ```
5. **Capture results:** the worker should log `transcription_started/semantic_started`, move the WAV into `processed/`, and emit transcripts under `llm.whisper.transcript_output_root` (defaults to `watch_roots/transcripts`).
6. **Repeat (optional)** with the second clip to compare timing/accuracy. Record `processing_ms`, detected language/confidence, and transcript snippets in `pm/status_logs/` when closing M02-T02a.

This README reflects every unit module currently in `tests/unit/` so contributors can quickly map specs to executable coverage.````markdown
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
- `test_transcription_worker.py` — Validates the EF-02 worker’s success/failure paths, ensuring transcripts persist to EF-06, downstream jobs are queued, and INF-04 retryable faults update pipeline status appropriately.

## Local Watch Roots

The `watch_roots/` directory is **not** tracked in git because developers frequently stage large media files or mount external volumes during ETS runs. Before exercising EF-01 watchers locally, run:

```powershell
python scripts/setup_watch_roots.py
```

This script creates the default `audio/` and `documents/` trees (each with `incoming`, `processing`, `processed`, and `failed` subfolders) plus convenience directories such as `watch_roots/transcripts`. If you prefer storing watch roots elsewhere, update your INF-01 profile (`capture.watch_roots[].root_path`) after generating the initial structure.

## Spec Markers & Targeted Runs

Each unit module declares a `# Coverage: ...` comment alongside `pytestmark` entries so that suites can be filtered by spec identifiers. The available markers are defined in `pytest.ini` (`ef01`, `ef02`, `ef06`, `ef07`, `inf01`, `inf02`, `inf04`). Examples:

- Run all EF-01 capture + watcher tests: `pytest -m ef01 tests/unit`
- Focus on EF-06 datastore behaviors: `pytest -m ef06 tests/unit`
- Combine predicates (EntryStore touching the job queue): `pytest -m "ef06 and inf02" tests/unit`

Use these filters during milestone sign-off or while iterating on a specific subsystem to avoid running the entire unit suite.

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

## EF-02 Whisper ETS Guidance

Real-media validation for M02-T02a uses the two bundled WAV clips located in `watch_roots/audio/incoming/` (`20250907115516.WAV` and `20250908132309.WAV`). Follow the sequence below to prove the faster-whisper integration end-to-end:

1. **Configure Whisper:** set `ECHOFORGE_WHISPER_ENABLED=1` (or update your YAML profile) and ensure the optional dependency `faster-whisper` is installed. Adjust `ECHOFORGE_WHISPER_MODEL_ID`, `ECHOFORGE_WHISPER_DEVICE`, etc., if you are targeting GPU hardware.
2. **Unit/marker sweep:** run `pytest -m "ef02 and inf04" tests/unit/test_llm_gateway.py tests/unit/test_transcription_worker.py` to cover the gateway wrapper plus worker error handling before touching real media.
3. **Stage sample audio:** copy one of the WAV fixtures from `watch_roots/audio/incoming` into `watch_roots/audio/processing` (the worker expects to move files from `processing/` → `processed/`). Example PowerShell:
   ```powershell
   Copy-Item watch_roots/audio/incoming/20250907115516.WAV watch_roots/audio/processing/
   ```
4. **Run the worker manually for ETS:** from the repo root launch a Python shell with the workspace on the `PYTHONPATH` and invoke the worker directly:
   ```powershell
   $env:PYTHONPATH='d:\@EchoForge_v3'
   python - <<'PY'
   from backend.app.jobs import transcription_worker
   payload = {
       "entry_id": "ETS-demo-entry",
       "source_path": r"d:\\@EchoForge_v3\\watch_roots\\audio\\processing\\20250907115516.WAV",
       "source_channel": "watch_folder_audio",
       "fingerprint": "ets-demo-fp",
       "media_type": "audio/wav",
       "language_hint": "en",
       "llm_profile": "transcribe_v1",
       "correlation_id": "ets-whisper-001",
   }
   transcription_worker.handle(payload)
   PY
   ```
   The worker logs `transcription_started`/`transcription_completed`, moves the WAV into `watch_roots/audio/processed/`, writes segment metadata to the in-memory EntryStore, and enqueues `echo.normalize_entry` for downstream EF-04.
   Transcripts are emitted to the directory configured via `llm.whisper.transcript_output_root` (defaults: `watch_roots/transcripts` for Shape A, `~/.echoforge/transcripts` for Shape B) and referenced in EF-06 `verbatim_path`.
5. **Repeat for the second clip** (optional) to compare timings or model accuracy. Capture the elapsed `processing_ms` plus detected language/confidence in your ETS notes.

Document ETS outcomes (success timestamps, resulting transcript snippets, any deviations) inside `pm/status_logs/` when closing out M02-T02a.

````# EchoForge Tests

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
- `test_transcription_worker.py` — Validates the EF-02 worker’s success/failure paths, ensuring transcripts persist to EF-06, downstream jobs are queued, and INF-04 retryable faults update pipeline status appropriately.

## Spec Markers & Targeted Runs

Each unit module declares a `# Coverage: ...` comment alongside `pytestmark` entries so that suites can be filtered by spec identifiers. The available markers are defined in `pytest.ini` (`ef01`, `ef02`, `ef06`, `ef07`, `inf01`, `inf02`, `inf04`). Examples:

- Run all EF-01 capture + watcher tests: `pytest -m ef01 tests/unit`
- Focus on EF-06 datastore behaviors: `pytest -m ef06 tests/unit`
- Combine predicates (EntryStore touching the job queue): `pytest -m "ef06 and inf02" tests/unit`

Use these filters during milestone sign-off or while iterating on a specific subsystem to avoid running the entire unit suite.

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
