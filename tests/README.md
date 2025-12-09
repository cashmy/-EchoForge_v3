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
- ETS pipeline harness (EF-02 → EF-05): `pytest -m ets_pipeline tests/ets`

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
- **INF-03 logging sweep** — `py -m pytest tests/unit/test_transcription_worker.py tests/unit/test_extraction_worker.py tests/unit/test_normalization_worker.py tests/unit/test_semantic_worker.py` (uses `tests/helpers/logging.py` to confirm `*_started`, `*_completed`, `*_failed` records include `stage`, `pipeline_status`, `correlation_id`, timing data, and worker-specific counters before any ETS dry run).
- **Transcription + Whisper gateway** — `test_transcription_worker.py`, `test_llm_gateway.py`, `test_whisper_client.py`
- **Document extraction** — `test_ef03_extraction_service.py`, `test_extraction_worker.py`
- **Normalization** — `test_normalization_worker.py`
- **Semantic enrichment** — `test_semantic_worker.py`
   - `summarize_v1` auto mode (<6k chars) proving deep-mode prompts + summary/title persistence.
   - Forced `preview` mode (>6k chars) verifying prompt truncation, capture events, and metadata input counts.
   - `classify_v1` rerun ensuring summaries remain intact while tags/type/domain update with hints.
   - Structured logging coverage asserting `semantic_job_started`, `semantic_job_completed`, and `semantic_job_failed` include entry/mode/profile/error metadata for INF-03 traceability.
   - **Pipeline Guardrails:** EF-05 tests **must** create entries via the EF-06 gateway and walk pipeline transitions with the `PIPELINE_STATUS` constants before queueing semantics work. Reuse `_create_semantics_ready_entry` in `test_semantic_worker.py` (or the same pattern elsewhere) to advance an entry through transcription → normalization so that the in-memory gateway’s ingest-state enforcement stays aligned with production. This prevents invalid `queued_for_semantics` bootstraps and keeps capture metadata/pipeline history realistic.
   - **INF-03 pipeline logging sweeps:** `tests/helpers/logging.py` exposes `RecordingLogger`, `find_log`, and assertion helpers to verify that EF-02→EF-05 emit `*_started`, `*_completed`, and `*_failed` entries with `stage`, `pipeline_status`, `correlation_id`, timing metrics, and worker-specific counters (segment_count, chunk_count, etc.). Run `py -m pytest tests/unit/test_transcription_worker.py tests/unit/test_extraction_worker.py tests/unit/test_normalization_worker.py tests/unit/test_semantic_worker.py` before ETS dry runs so structured logging regressions surface immediately.

#### M02 Pipeline ETS Matrix

| Scenario ID | Setup / Inputs | Execution Path | Expected Observables | Notes |
| --- | --- | --- | --- | --- |
| A1 — Audio happy path | Stage `watch_roots/audio/processing/20250907115516.WAV`, ensure INF-02 queue delivers `echo.transcribe_audio` and downstream jobs (`echo.normalize_entry`, `echo.semantic_enrich`). Use Shape A config with Whisper enabled. | Run watcher or manually invoke EF-02 → EF-03 → EF-04 → EF-05 via `python -m backend.app.jobs.<worker> handle` payloads, passing the previous job’s outputs (see `tests/unit/test_transcription_worker.py::_create_entry`). | EF-06 entry advances from `queued_for_transcription` → `semantic_complete`, capture events logged for each stage, INF-03 logs include correlation IDs, semantic summary/title populated, `watch_roots/transcripts` contains verbatim file. | Record timings (`processing_ms`, duration) and summarize in `pm/status_logs/` when closing M02-T12 dry run. |
| D1 — Document OCR / extraction chain | Place multi-page scanned PDF in `watch_roots/documents/processing`, set `ocr_mode=auto`. Ensure INF-01 `documents.segment_cache_root` configured. | Trigger EF-03 via watcher or direct call; allow EF-04/05 jobs to follow automatically. | EF-06 shows `extraction_metadata.ocr_used=true`, segment cache artifact referenced, normalization metadata includes segment_count and chunk_count, semantic job runs in preview mode (>6k chars). | Validates document pipeline plus idempotent chunk counts; capture logs must include stage='extraction' and OCR flags. |
| R1 — Retryable transcription fault | Use smaller WAV, monkeypatch INF-04 Whisper client (or set `ECHOFORGE_WHISPER_FORCE_RATE_LIMIT=1`) to emit `llm_rate_limited` on first attempt. | Run EF-02 job; allow automatic retry (INF-02) or re-invoke manually with `retry_count=1`. | WARN-level `transcription_retry_scheduled` log emitted, capture metadata records `retryable=true`, final success transitions pipeline to normalization. | Confirms retry telemetry; if final attempt fails, EF-06 last_error should still mark retryable. |
| F1 — Extraction terminal failure | Provide password-protected PDF. | Run EF-03 job; expect immediate failure without downstream jobs. | EF-06 pipeline_status=`extraction_failed`, capture metadata logs `password_protected`, INF-03 error log contains `retryable=false`. | Ensure INF-02 dead-letters job; record artifact path under `failed/documents`. |
| S1 — Semantic-only rerun (classify_v1) | Use entry already normalized and summarized; enqueue `echo.semantic_enrich` with `operation="classify_v1"` and `classification_hint`. | Invoke EF-05 only. | Summary/title unchanged, but `semantic_tags`, `type_label`, `domain_label`, and classification metadata update; logs show `semantic_rerun=true`. | Confirms idempotent semantic updates and hints propagation. |
| I1 — Idempotent re-run after failure | Take entry stuck at `normalization_failed`, fix root cause (e.g., missing text) and requeue normalization job with same correlation ID. | Run EF-04 followed by EF-05 manually. | EF-06 history reflects second attempt, capture metadata records recovery event, semantic job enqueues once. | Validates state transitions + job dedupe across retries. |

Use this matrix to drive ETS rehearsals: seed the specified artifacts, walk the pipeline manually or via watchers, and log outcomes under `pm/status_logs/Status_Log_M02_*.md`. Each scenario should include screenshots or log excerpts when possible so MG06 governance can audit the dry run.

##### Deterministic Fixture Placement

Deterministic fixtures for the matrix live in `tests/fixtures/ets_pipeline/` and can be staged automatically:

1. Ensure watch roots exist: `python scripts/setup_watch_roots.py`
2. Generate fixtures and copy them into the watch roots:
   ```powershell
   python scripts/setup_ets_fixtures.py --copy-to-watch-roots
   ```
   - Audio inputs → `watch_roots/audio/incoming/20250907115516.wav` and `20250908132309.wav`
   - Document inputs → `watch_roots/documents/incoming/doc_pipeline_reference.txt` and `doc_ocr_simulation.txt`
3. Semantic-only reruns consume `tests/fixtures/ets_pipeline/payloads/normalized_snapshot.json`; keep it under version control for reproducibility.

See `tests/fixtures/ets_pipeline/README.md` for fixture descriptions, scenario mappings, and refresh instructions.

##### Automated ETS Harness (M02)

- Harness helper + stubs live in `tests/helpers/pipeline_harness.py`; see `tests/ets/test_pipeline_harness.py` for the executable scenarios.
- The harness drives EF-02 (audio) and EF-03 (document) entries through EF-04/EF-05, asserting INF-03 logging on both happy-path and semantic-failure runs.
- Run the suite directly with `pytest -m ets_pipeline tests/ets` or via `python scripts/ets_runner.py --profile pipeline` to integrate with CI/dev workflows.
- Keep this suite green before staging manual ETS rehearsals so regressions surface prior to watcher-driven dry runs referenced in the matrix above.

##### Operator ETS Rehearsal Procedure (M02-T12)

1. **Pre-flight gate.** Run the deterministic checks before touching watch roots:
   ```powershell
   python scripts/setup_watch_roots.py
   python scripts/setup_ets_fixtures.py --copy-to-watch-roots
   python scripts/ets_runner.py --profile pipeline
   $env:PYTHONPATH='d:\@EchoForge_v3'; py -m pytest tests/unit/test_transcription_worker.py tests/unit/test_extraction_worker.py tests/unit/test_normalization_worker.py tests/unit/test_semantic_worker.py
   ```
   These commands verify folder layout, stage the fixtures listed in the matrix, prove the ETS harness is green, and re-run the INF-03 logging sweep.

2. **Stage per-scenario inputs.** Use the matrix above to decide which artifacts to promote from `watch_roots/<channel>/incoming` into `processing/`:
   - Audio scenarios (A1, R1) → `Move-Item watch_roots/audio/incoming/20250907115516.wav watch_roots/audio/processing/` (repeat with `20250908132309.wav` if needed).
   - Document scenarios (D1, F1) → `Move-Item watch_roots/documents/incoming/doc_pipeline_reference.txt watch_roots/documents/processing/` (swap in `doc_ocr_simulation.txt` for OCR/Failure cases).
   - Semantic-only scenarios (S1) → load `tests/fixtures/ets_pipeline/payloads/normalized_snapshot.json` into an EF-06 entry (via API or gateway helper) so EF-05 can be invoked directly; reuse failed normalization entries for I1 reruns.

3. **Kick the job chain.** Execute one watcher scan to register the staged files and enqueue jobs, then manually walk the workers so telemetry can be captured deterministically:
   ```powershell
   python scripts/run_watch_once.py
   $env:PYTHONPATH='d:\@EchoForge_v3'
   python - <<'PY'
   from backend.app.jobs import transcription_worker, normalization_worker, semantic_worker
   # Replace ENTRY_ID / PATH values with the IDs surfaced by the watcher + INF-02 queue payloads.
   payload = {
       "entry_id": "<ENTRY_ID>",
       "source_path": r"d:\\@EchoForge_v3\\watch_roots\\audio\\processing\\20250907115516.wav",
       "source_channel": "watch_folder_audio",
       "fingerprint": "ets-a1",
       "media_type": "audio/wav",
       "language_hint": "en",
       "llm_profile": "transcribe_v1",
       "correlation_id": "ets-a1-001",
   }
   transcription_worker.handle(payload)
   normalization_worker.handle({"entry_id": payload["entry_id"], "source": "transcription", "correlation_id": payload["correlation_id"]})
   semantic_worker.handle({"entry_id": payload["entry_id"], "correlation_id": payload["correlation_id"]})
   PY
   ```
   Swap in `extraction_worker.handle(...)` for document-driven scenarios and rerun semantic-only jobs with `operation="classify_v1"` + `classification_hint` when exercising S1.

4. **Verify artifacts & telemetry.** After each worker finishes:
   - Confirm `watch_roots/<channel>/processed/` (or `failed/`) contains the promoted fixture.
   - Inspect EF-06 via API/SQL to ensure `pipeline_status` advanced (`transcription_complete` → `semantic_complete`) and that capture events list `*_started`/`*_completed` plus retries when applicable.
   - Tail console output for `transcription_*`, `extraction_*`, `normalization_*`, and `semantic_job_*` logs; they must include `entry_id`, `stage`, `pipeline_status`, and `correlation_id` to satisfy INF-03.

5. **Record the rehearsal.** Summarize each scenario’s timestamps, `processing_ms`, retry counts, and notable log excerpts inside `pm/status_logs/Status_Log_M02_<date>.md`, referencing the scenario IDs (A1, D1, R1, F1, S1, I1). Attach any anomalies or follow-up actions before marking M02-T12 as complete.

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

---

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
