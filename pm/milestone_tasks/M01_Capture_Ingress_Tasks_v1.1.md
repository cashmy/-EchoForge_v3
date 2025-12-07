# M01 — Capture & Ingress Tasks — v1.1

---

## 0. Metadata

- **Milestone ID:** M01  
- **Milestone Name:** Capture & Ingress  
- **Scope Summary:**  
  Establish a robust, idempotent ingestion path for EchoForge v3 from watched folders, manual/UI text, and API-based capture, wired through EF-01 → EF-06 → INF-02, and exposed via EF-07’s `/capture` endpoint.  
- **Primary Components:**  
  - EF-01 CaptureService  
  - EF-06 EntryStore  
  - EF-07 API (capture-related subset)  
  - INF-02 JobQueueService  
  - INF-03 LoggingService  
- **Related Governance / Protocol Artifacts:**  
  - Milestone_Task_Subsystem_v1.1.md  
  - Codex_LLM_Engagement_Protocol_v1.0.md  
  - EnaC_TestingSubsystem_v1.0.md  
  - Codex_Activation_Packet_v1.0.md  

---

## 1. Status Tracking Model (for Codex-LLM & Human Orchestrator)

Each task below includes a **Status Block** that is the *single source of truth* for tracking progress.

- **Status values (canonical):**
  - `pending` — not yet started  
  - `in_progress` — work has begun  
  - `blocked` — cannot proceed without decision/clarification  
  - `deferred` — intentionally postponed to a later pass  
  - `done` — task outcome satisfied per description  

- **Fields:**
  - **Status:** one of the canonical values above  
  - **Last Updated:** freeform timestamp or short note (e.g., `2025-12-06 by Codex`)  
  - **Notes:** short freeform progress note (optional)

Codex-LLM **MUST** only update these three fields inside each task’s Status Block when reflecting progress, postponements, or returns-to-work.

Example Status Block template:

```markdown
- **Status:** pending  <!-- pending | in_progress | blocked | deferred | done -->
- **Last Updated:** —
- **Notes:** —
- **Status:** done  <!-- pending | in_progress | blocked | deferred | done -->
- **Last Updated:** 2025-12-06 — GPT-5.1-Codex  
- **Notes:** EF06 `entries` table already carries `source_type`, `source_channel`, `source_path`, and pipeline/cognitive statuses. Missing explicit fingerprint fields (hash + algo) and watcher metadata to satisfy EF-01 idempotency. Need new columns (e.g., `capture_fingerprint`, `fingerprint_algo`, optional JSONB metadata) or a capture-tracking table in a follow-up task. Map EF-01 ingest states onto existing `pipeline_status` values (e.g., `ingested` ⇔ `captured`).  
```

---

## 2. References

The following artifacts MUST be consulted before and during work on this milestone:

- `EchoForge_Architecture_Overview_v1.1.md`  
- `EchoForge_Component_Summary_v1.1.md`  
- `EchoForge_Scope_and_Boundaries_v1.1.md`  
- `EchoForge_Milestone_Summary_v1.2.md`  
- `EF01_CaptureService_Interfaces_Spec_v1.1.md`  
- `EF06_EntryStore_Spec_v1.1.md`  
- `EF07_Api_Contract_v1.1.md`  
- `INF02_JobQueueService_Spec_v1.0.md`  
- `INF03_LoggingService_Spec_v1.0.md`  

Codex-LLM MUST NOT infer architecture or behavior beyond what is described in these artifacts.

---

## 3. Tasks

> **Note:** All Status Blocks are initially set to `pending`. Codex-LLM and/or the human orchestrator will update them over time.

---

### M01-T01 — Confirm EF-06 EntryStore Schema for Ingestion

- **Type:** design  
- **Depends On:** —  
- **ETS Profiles:** —  
- **Status Block:**
  - **Status:** done  <!-- pending | in_progress | blocked | deferred | done -->
  - **Last Updated:** 2025-12-06 — GPT-5.1-Codex  
  - **Notes:** Added `ensure_watch_roots_layout` helper plus startup hook so every configured watch root materializes `incoming/processing/processed/failed` subfolders. Tests in `tests/unit/test_watch_folders.py` cover scaffolding behavior.  

**Description:**  
Review `EF06_EntryStore_Spec_v1.1.md` and confirm that all fields required by EF-01 for capture are present and well-defined, including (but not limited to) `source_type`, `source_channel`, `source_path`, `ingest_state`, and timestamps.  
Identify and document any gaps or ambiguities that would block EF-01 from creating Entries cleanly.

---

### M01-T02 — Define Ingestion-Related Indexes / Query Patterns

- **Type:** design  
- **Depends On:** M01-T01  
- **ETS Profiles:** —  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-06 — GPT-5.1-Codex  
  - **Notes:** Add unique index once fingerprint columns land: `IDX_entries_fingerprint_channel ON entries (capture_fingerprint, source_channel)` for EF-01 idempotency. Add supporting indexes `IDX_entries_source_path ON entries (source_path)` and `IDX_entries_source_channel ON entries (source_channel)` to cover watch-path replays and manual-text lookups.  

**Description:**  
Based on EF-01’s idempotency requirements, specify the minimal set of indexes or query patterns EF-06 must support for looking up Entries by:
- `source_channel`  
- `source_path`  
- ingestion fingerprint metadata (if stored)  

Output can be a short addition/annotation in the EF-06 spec or a note referenced from this milestone.

---

### M01-T03 — Implement EF-01 Folder Layout (incoming/processing/processed/failed)

- **Type:** implementation  
- **Depends On:** M01-T01  
- **ETS Profiles:** ETS-EF01-WATCH  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-06 — GPT-5.1-Codex  
  - **Notes:** Added `ensure_watch_roots_layout` helper plus startup hook so every configured watch root materializes `incoming/processing/processed/failed`. Unit tests cover scaffolding behavior.  

**Description:**  
Implement the physical folder layout for EF-01’s watch roots:

```text
watch_root/
  incoming/
  processing/
  processed/
  failed/
```

Ensure configuration is read from the appropriate config source (INF-01 if applicable) and that no hard-coded absolute paths are embedded in code.

---

### M01-T04 — Implement EF-01 Capture Fingerprint and Idempotency Check

- **Type:** implementation  
- **Depends On:** M01-T01, M01-T03  
- **ETS Profiles:** ETS-EF01-WATCH, ETS-EF01-JQ  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-06 — GPT-5.1-Codex  
  - **Notes:** Implemented `compute_file_fingerprint` + `evaluate_idempotency` helpers with dedicated tests (`tests/unit/test_fingerprint.py`, `tests/unit/test_idempotency.py`). Logic now centralizes EF-06 lookup + skip/ retry decisions.  

**Description:**  
Implement the fingerprint computation and idempotency check described in `EF01_CaptureService_Interfaces_Spec_v1.1.md`, including:
- Computing a stable fingerprint for watched files (e.g., name + size + mtime and/or content hash).  
- Checking EF-06 (or a dedicated capture table) for an existing Entry with matching fingerprint and `source_channel`.  
- Skipping re-processing for Entries whose `ingest_state` is `processing` or `processed`.  

---

### M01-T05 — Implement EF-01 Watcher Integration

- **Type:** implementation / wiring  
- **Depends On:** M01-T03, M01-T04  
- **ETS Profiles:** ETS-EF01-WATCH  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** `WatcherOrchestrator` now ships with runtime adapters (`InMemoryEntryGateway`, `InfraJobQueueAdapter`) plus CLI `scripts/run_watch_once.py`. Unit coverage across `tests/unit/test_watcher_orchestrator.py` and `test_watcher_runtime.py` proves folder moves + job enqueue wiring.  

**Description:**  
Implement the watcher logic that:
- Observes `incoming/` directories for new files.  
- Calls the `on_file_detected(path)`-style function as specified in EF-01.  
- Moves accepted files to `processing/` and rejects/flags unsupported inputs.  
- Handles basic error conditions gracefully (e.g., unreadable files).

---

### M01-T06 — Implement EF-01 → EF-06 Entry Creation

- **Type:** implementation  
- **Depends On:** M01-T01, M01-T04, M01-T05  
- **ETS Profiles:** ETS-EF01-WATCH, ETS-EF01-API  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Added EF-06 gateway models + in-memory adapter (`backend/app/domain/ef06_entrystore/`) and rewired EF-01 watcher/runtime to create Entries via `EntryCreateRequest`. Unit tests (`test_entrystore_gateway.py`, `test_watcher_orchestrator.py`, `test_watcher_runtime.py`) confirm source metadata + pipeline defaults persist correctly. Implementation rationale (dataclass-per-boundary approach) documented in `pm/decisions/2025-12-07_entry_model_boundary.md`.  

**Description:**  
Implement the EF-01 internal integration that calls EF-06 to create a new Entry for:
- Watcher-based ingestion (audio and documents).  

Ensure `source_type`, `source_channel`, `source_path`, `ingest_state`, and relevant metadata (e.g., fingerprint) are persisted exactly as per spec.

---

### M01-T07 — Implement EF-01 → INF-02 Job Enqueue for Transcription/Extraction

- **Type:** implementation / wiring  
- **Depends On:** M01-T06  
- **ETS Profiles:** ETS-EF01-JQ  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** `WatcherOrchestrator` now routes accepted files through `InfraJobQueueAdapter`, emitting `transcription` / `doc_extraction` jobs with `{entry_id, source_path}` payloads. After enqueue, EF-06 gateway updates each Entry’s pipeline status to `queued_for_transcription`/`queued_for_extraction`, keeping idempotency checks aligned. Covered by `tests/unit/test_watcher_orchestrator.py` and `test_watcher_runtime.py`.  

**Description:**  
Implement EF-01 integration with INF-02 such that:
- Audio files enqueue a `transcription` job with payload containing `entry_id` and `source_path`.  
- Document files enqueue a `doc_extraction` job with appropriate payload.  
- `ingest_state` is updated to `queued_for_transcription` or `queued_for_extraction` as appropriate.

---

### M01-T08 — Implement Manual Text Capture Path (`capture_manual_text`)

- **Type:** implementation  
- **Depends On:** M01-T01  
- **ETS Profiles:** ETS-EF01-API  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Added `capture_manual_text` helper (`backend/app/domain/ef01_capture/manual.py`) to hash text payloads, stamp metadata, and create EF-06 entries with `source_type="text"`. Covered by `tests/unit/test_manual_capture.py` and `/api/capture` text-mode tests.  

**Description:**  
Implement the manual text capture function in EF-01 (or equivalent service layer) that:
- Accepts raw text and optional metadata.  
- Creates an Entry in EF-06 with `source_type = "text"` and `source_channel = "manual_text"` (or equivalent).  
- Does not enqueue transcription/extraction jobs, but remains compatible with later normalization (EF-04).

---

### M01-T09 — Implement EF-07 `/capture` Endpoint (HTTP → EF-01)

- **Type:** implementation / wiring  
- **Depends On:** M01-T06, M01-T08  
- **ETS Profiles:** ETS-EF01-API  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** `/api/capture` router now accepts `text` and `file_ref` modes, wiring EF-01 manual capture + file-fingerprint/idempotency logic, INF-02 enqueue, and queued status updates. Exercised via `tests/unit/test_capture_api.py`.  

**Description:**  
Implement `POST /api/v1/capture` as defined in `EF07_Api_Contract_v1.1.md`, including:
- `mode = "text"` → delegates to EF-01 manual text capture.  
- `mode = "file_ref"` → delegates to EF-01 as if a watcher event with server-side `file_path`.  
- Proper validation and mapping of error conditions into EF-07 error codes.  

---

### M01-T10 — Wire Logging (INF-03) for EF-01 Ingestion Path

- **Type:** implementation  
- **Depends On:** M01-T04, M01-T05, M01-T07, M01-T09  
- **ETS Profiles:** ETS-EF01-WATCH, ETS-EF01-API, ETS-EF01-JQ  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Added INF-03 logger usage across EF-01 watcher (`watcher.py`), manual capture helper (`manual.py`), and `/api/capture` router so successful ingests, idempotent skips, validation failures, unsupported files, and job enqueue errors emit structured messages. Covered by existing unit suite (`tests/unit/test_capture_api.py`, `test_watcher_orchestrator.py`).  

**Description:**  
Ensure that all key EF-01 ingestion events and errors are logged via INF-03, including:
- Successful capture of new files/text.  
- Idempotent skips.  
- Job enqueue failures.  
- Validation failures and unsupported file types.  

---

### M01-T11 — Define and Implement ETS Test Cases for M01

- **Type:** test  
- **Depends On:** M01-T03 through M01-T10  
- **ETS Profiles:** ETS-EF01-WATCH, ETS-EF01-API, ETS-EF01-JQ  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Documented ETS-aligned unit coverage in `tests/README.md` mapping watch folder lifecycle, idempotency skips, entry creation metadata, INF-02 job handoff, and `/api/capture` flows to specific test modules (`pytest tests/unit`). No additional harness needed for M01 scope.  

**Description:**  
For the ETS profiles relevant to EF-01 and capture, define and/or implement concrete test cases that verify:
- Folder lifecycle behavior (`incoming/` → `processing/` → `processed/` / `failed/`).  
- Idempotency on repeated files.  
- Correct creation of Entries for different `source_type` / `source_channel` combinations.  
- Proper handoff to INF-02 and error handling.  
- `/capture` endpoint behavior for both `text` and `file_ref` modes.

---

### M01-T12 — Create Initial Status Log for M01

- **Type:** governance  
- **Depends On:** At least M01-T03, M01-T04, M01-T05 in some form  
- **ETS Profiles:** —  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Logged `pm/status_logs/Status_Log_M01_2025-12-07.md` covering completed tasks (T01–T11), remaining governance work (T12–T13), open schema tensions, and follow-on actions per MTS v1.1.  

**Description:**  
Using the Milestone Task Subsystem protocol, create an initial status log entry in `pm/status_logs/` describing:
- Which M01 tasks have been started or completed.  
- Any open questions or decisions required.  
- Any observed architectural tensions, to be considered in later milestones.

---

### M01-T13 — Identify Decisions Requiring Human Approval

- **Type:** governance  
- **Depends On:** M01-T03 through M01-T11 (as executed)  
- **ETS Profiles:** —  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Captured schema + config assumptions in `pm/decisions/2025-12-07_ef06_fingerprint_schema.md` (adds Entry fingerprint columns) and `pm/decisions/2025-12-07_capture_config_profiles.md` (documents required Config Service profiles for watch roots/manual hashing). No further approvals requested yet.  

**Description:**  
Review M01 implementation work and identify any decisions that:
- Deviated from the specs.  
- Introduced new assumptions (e.g., naming, directory layout nuances, or fingerprint strategies).  
- Might impact future milestones (e.g., semantics, UI expectations).  

Capture these as entries in `pm/decisions/` for human review and approval.

---

## 4. Exit Criteria for M01

M01 is considered **complete** when:

1. EF-01 can reliably ingest:
   - New audio and document files dropped into `incoming/` and move them through to `processing/`.  
   - Manual text via an internal/EF-01 call.  
   - API-based capture via EF-07’s `/capture` endpoint.  

2. EF-06 Entries are created consistently with all required ingestion metadata and `ingest_state` transitions.

3. INF-02 receives transcription/extraction jobs with correct payloads.

4. Logging via INF-03 provides a traceable story for ingestion events and errors.

5. ETS tests for EF-01 and capture paths have been defined and at least a minimal core set executed.

6. A status log and any required decisions have been recorded under `pm/status_logs/` and `pm/decisions/`.

Once these conditions are met and reviewed by the human orchestrator, Codex-LLM may be directed (via the Engagement Protocol and Activation Packet) to proceed to the next milestone.
