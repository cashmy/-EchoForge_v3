# M02 — Processing Pipeline (Transcription, Extraction, Normalization, Semantics) — v1.0

---

## 0. Metadata

- **Milestone ID:** M02  
- **Milestone Name:** Processing Pipeline  
- **Scope Summary:**  
  Implement the full asynchronous processing pipeline triggered after ingestion:  
  - EF-02 TranscriptionService (audio → text)  
  - EF-03 DocumentExtractionService (docs → extracted text)  
  - EF-04 NormalizationService (cleaning, structure, preprocessing)  
  - EF-05 GptEntrySemanticService (LLM-based semantic enrichment)  
  All coordinated via INF-02 JobQueue and persisted into EF-06 EntryStore.  
- **Primary Components:**  
  - EF-02, EF-03, EF-04, EF-05  
  - INF-02 (JobQueue)  
  - INF-04 (LLM Gateway)  
  - EF-06 (EntryStore)  
- **Governance Artifacts:**  
  - MTS v1.1  
  - ETS v1.0  
  - Codex Engagement Protocol  
  - Activation Packet  

---

## 1. Task Tracking Framework  
Every task MUST contain a **Status Block**:

```markdown
- **Status:** pending  <!-- pending | in_progress | blocked | deferred | done -->
- **Last Updated:** —
- **Notes:** —
```

Codex-LLM MUST only edit these three fields when updating status.  
For deeper planning, add an optional **Subtasks** section directly beneath the Description:

```markdown
#### Subtasks
- [ ] ST01 — Short label (link to detailed plan doc)
- [ ] ST02 — …
```

- Use the checklist for governance-visible tracking.  
- Link each line to a supporting plan/ETS document (`pm/milestone_tasks/M03_T01_Subtask_Plan.md`, etc.) where detailed research, test matrices, and notes live.  
- Keep the milestone file concise; put expanded rationale, research, and test plans in the linked document.

---

## 2. References

- `EF01_CaptureService_Interfaces_Spec_v1.1.md`  
- `EF02_TranscriptionService_Spec` (implicit via EF architecture; Codex to generate if missing)  
- `EF03_DocumentExtractionService_Spec`  
- `EF04_NormalizationService_Spec`  
- `EF05_GptEntrySemanticService_Spec_v1.0.md`  
- `EF06_EntryStore_Spec_v1.1.md`  
- `INF02_JobQueueService_Spec_v1.0.md`  
- `INF04_LlmGateway_Spec_v1.0.md`  
- `EchoForge_Architecture_Overview_v1.1.md`

---

## 3. Tasks

---

### M02-T01 — Define EF-02 Transcription Input/Output Contract

- **Type:** design  
- **Depends On:** M01 completion  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Defined EF-02 contract (job type, payload, EF-06 fields, error map, timing) below; ready for worker implementation.  

**Description:**  
Specify the exact EF-02 contract: input payload, text result structure, error codes, timing expectations, and EF-06 update requirements (`transcription_text`, `ingest_state` transitions).

**Contract Outline:**
- **Job Type:** `echo.transcribe_audio` (alias `transcription`) handled via INF-02. All enqueue calls MUST include a `correlation_id` propagated from EF-01 logging context.
- **Payload Schema:**
  - `entry_id` *(UUID, required)* — EF-06 entry to update.
  - `source_path` *(string, required)* — absolute processing-path for the audio file (EF-01 moves files into `processing/`).
  - `source_channel` *(string, required)* — e.g., `watch_folder_audio`, `manual_upload_audio` for logging + EF-06 metadata.
  - `media_type` *(enum: `audio/wav`, `audio/mpeg`, etc.)* — informs decoder.
  - `fingerprint` *(string, required)* — capture fingerprint for traceability.
  - `language_hint` *(ISO code, optional)* and `llm_profile` *(defaults to `transcribe_v1`)* to steer INF-04.
  - `retry_count` *(int, optional)* — INF-02 populates to help EF-02 decide between retry vs. fail.
- **Execution Requirements:**
  - Worker loads the media from `source_path`, streams it through INF-04 -> Whisper/LLM provider using profile `transcribe_v1`.
  - Must produce a normalized transcript payload: `text` (full transcript string) + optional `segments` array (timestamped chunks) for downstream EF-04.
  - Capture metrics: duration seconds, detected language, confidence, model name, processing_ms.
- **EF-06 Updates:**
  - Transition `pipeline_status`: `queued_for_transcription` → `transcription_in_progress` when worker starts; `transcription_complete` on success; `transcription_failed` on terminal error.
  - Persist fields:
    - `transcription_text` (full string)
    - `transcription_segments` (JSONB array, optional)
    - `transcription_metadata` (JSONB) containing language, confidence, model, processing_ms, worker_id.
    - Update `updated_at` timestamp and attach audit trail to `metadata.capture_events[].`
- **Error & Retry Semantics:**
  - Classify failures into `media_unreadable`, `llm_timeout`, `llm_rate_limited`, `unsupported_format`, `internal_error`.
  - For recoverable errors (`llm_timeout`, `llm_rate_limited`) return `retryable=true`; INF-02 retries per config.
  - On non-recoverable errors, mark EF-06 `pipeline_status = transcription_failed`, populate `transcription_error_code`, and write INF-03 log with correlation ID and fingerprint.
- **Timing Expectations / SLAs:**
  - Target ≤ real-time for ≤15 min clips on ShapeA/ShapeB. If audio exceeds 30 min, worker MUST chunk and emit partial logs every 5 min.
  - Worker must respect INF-02 default retry attempts (3) and escalate via decision log if SLOs cannot be met.
- **Downstream Notifications:**
  - After success, enqueue normalization job (`echo.normalize_entry`) with payload `{entry_id, source=transcription}` to trigger EF-04 per pipeline diagrams.
  - Emit INF-03 structured log events: `transcription_started`, `transcription_completed`, `transcription_failed` with correlation + entry IDs.

---

### M02-T02 — Implement EF-02 Transcription Worker

- **Type:** implementation  
- **Depends On:** M02-T01  
- **ETS Profiles:** ETS-Pipeline, ETS-LLM  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** EF-02 worker now enforces INF-04 timing metadata, capture events, and file rollover to processed/failed paths per spec.  

**Description:**  
Implement the worker that consumes a `transcription` job, invokes whisper/LLM STT through INF-04, updates EF-06, and moves files to processed/failed.

---

### M02-T02a — Replace INF-04 Transcription Stub with Whisper Integration

- **Type:** implementation  
- **Depends On:** M02-T02  
- **ETS Profiles:** ETS-Pipeline, ETS-LLM  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Whisper integration live; governance captured in `2025-12-07_inf04_whisper_integration.md` and `pm/status_logs/Status_Log_M02_2025-12-07.md`.  

**Description:**  
Replace the stubbed `transcribe_audio` helper with a real Whisper-backed INF-04 implementation, including model/config plumbing, error taxonomy, and ETS guidance for large WAV fixtures.

Sub tasks (remaining): 
- ✅ INF-04 gateway wiring – replace the stubbed transcribe_audio entry point (likely __init__.py) so it calls whisper_client.transcribe_file, translates exceptions into the error taxonomy from M02-T01, and exposes metrics (model, duration, language).
- ✅ Configuration plumbing – ensure .env/config docs cover all Whisper knobs (ECHOFORGE_WHISPER_*), add safe defaults to settings loaders, and make sure is_available() respects deployment toggles so non-Whisper environments fail fast.
- ✅ Worker integration – update transcription_worker.py (or the corresponding service) to invoke the new INF-04 method, capture transcript/segments/metadata, and persist them in EF-06 according to the contract.
- ✅ Testing + fixtures – add unit tests around the gateway wrapper and worker error cases, plus ETS guidance for the two provided WAV samples (end-to-end dry run proving the audio files transcribe successfully).
- Docs & governance – log the Whisper integration decision (already referenced) but finalize any follow-up notes in status_logs and update the M02-T02a status block once tests pass.

---

### M02-T02b — Externalize EF-02 Transcripts to Filesystem

- **Type:** implementation  
- **Depends On:** M02-T02a  
- **ETS Profiles:** ETS-Pipeline, ETS-LLM  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Transcript output root now lives in INF-01 profiles; EF-02 writes files + updates `verbatim_path`; see decisions `2025-12-07_transcript_output_root_profiles_only.md` and `2025-12-07_m02_t02b_transcript_externalization.md`.  

**Description:**  
Persist full transcription text (and optional segment JSON) as files on disk per INF-01 profile settings, then populate EF-06 `verbatim_path`/`verbatim_preview` fields so downstream components can fetch raw transcripts without bloating Entry rows.

Sub tasks (remaining):
- Config plumbing – extend INF-01 profiles/loader with `llm.whisper.transcript_output_root` (+ optional public URL), scaffold directories during watcher setup, and document the new knobs.
- Worker implementation – update `transcription_worker` to write transcript files atomically, roll them alongside media, and persist EF-06 verbatim metadata + retention hooks.
- Testing & ETS – add unit coverage for file emission and path recording, plus ETS instructions validating that transcripts land in the configured root and are linked in EF-06 entries.
- Docs & governance – update EF06 spec/addendum, config README, and status logs to reflect the externalized transcript behavior before promoting the task to `done`.

---

### M02-T03 — Define EF-03 Document Extraction Input/Output Contract

- **Type:** design  
- **Depends On:** M01  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Contract defined below; worker implementation (T04) can proceed.  


**Description:**  
Define EF-03 inputs/outputs for `.pdf`, `.docx`, `.txt`, `.md` ensuring extraction results flow into EF-06 and feed EF-04.

**Contract Outline:**
- **Job Type:** `echo.extract_document` (alias `document_extraction`) dispatched via INF-02. Jobs MUST carry the EF-01 `correlation_id` for traceability across INF-03 logs and EF-06 capture events.
- **Supported Formats:** `.pdf`, `.docx`, `.doc`, `.txt`, `.md`, `.rtf`. Scanned/bitmap PDFs require OCR with the `ocr_mode` flag enabled; workers MUST fail fast with `unsupported_format` when encountering anything outside this list.
- **Payload Schema:**
  - `entry_id` *(UUID, required)* — EF-06 row to mutate.
  - `source_path` *(string, required)* — absolute path under `processing/documents/` (EF-01 ensures staging).
  - `source_channel` *(string, required)* — watcher / upload origin for logging & retention hooks.
  - `source_mime` *(enum, required)* — e.g., `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.
  - `fingerprint` *(string, required)* — same capture fingerprint stored during ingestion for idempotency checks.
  - `page_range` *(string, optional)* — e.g., `"1-5,8"` to limit extraction, defaults to all pages.
  - `ocr_mode` *(enum: `auto`, `force`, `off`)* — controls OCR fallback for scanned PDFs; default `auto` (detects low text density and flips to OCR).
  - `retry_count` *(int, optional)* — provided by INF-02 to inform exponential backoff vs. terminal failure.
  - `llm_profile` *(string, optional)* — reserved for hybrid extractions that need LLM clean-up; defaults to `doc_extract_v1` but MAY be empty when pure parser.
  - `metadata_overrides` *(JSON, optional)* — per-entry switches (`skip_images`, `max_pages`, `redact_patterns`).

**Execution Requirements:**
- Worker transitions EF-06 `ingest_state` to `processing_extraction` as soon as the payload is accepted and updates `capture_metadata.capture_events[]` with `extraction_started` (timestamp, worker_id, source path, correlation id).
- For `.txt/.md`, stream the file directly; for `.docx/.pdf`, use the configured extractor stack (default: `python-docx`, `pdfminer.six`, and `tesseract` when OCR required). All temporary artifacts live under `processing/tmp/<entry_id>/` and MUST be deleted after success/failure.
- Output MUST include:
  - `extracted_text` *(string)* — full plain-text body.
  - `extraction_segments` *(JSON array)* — per-page/per-section objects: `{index, label, text, char_count, bbox?}` to help EF-04 chunk intelligently.
  - `extraction_metadata` *(JSON)* — `page_count`, `char_count`, `converter`, `ocr_language`, `parse_warnings`, `processing_ms`, `worker_id`.
- Large documents (>200k chars or >200 pages) MUST chunk writes to disk first, then stream into EF-06 to avoid memory issues; set `extraction_metadata.truncated=true` when enforcing size caps.
- **No STT/LLM involvement:** EF-03 remains a deterministic document-to-text stage. It MUST NOT invoke Whisper or any other speech-to-text service; likewise, it does not call INF-04. Its sole responsibility is converting existing document bytes into normalized text/preview artifacts. Any LLM usage (summaries, titles, semantic ops) occurs later via EF-05 once EF-03 has populated `extracted_text`.

**EF-06 Updates:**
- On start: `ingest_state = processing_extraction`, `pipeline_status = 'extraction_in_progress'` (mirrors EF-02 pattern). Worker records the `source_mime` under `capture_metadata.document.mime` if missing.
- On success: populate `extracted_text`, `extraction_segments` (JSONB), `extraction_metadata`, `content_lang` (if detected/overridden). Move state to `processing_normalization` and set `pipeline_status = 'extraction_complete'`. Generate a ~400-char preview from the start of `extracted_text` when `verbatim_preview` is empty.
- On failure: set `pipeline_status = 'extraction_failed'`, `ingest_state = failed`, and record `extraction_error_code` + `pipeline_detail`. Workers MUST leave the original file under `failed/documents/` for triage and reference it in `capture_metadata.capture_events[].artifact_path`.
- All writes occur inside a single transaction so `extracted_text` and `ingest_state` stay coherent per EF06 addendum §4.

**Filesystem & Retention:**
- INF-01 profiles introduce `documents.processed_root`, `documents.failed_root`, and `documents.segment_cache_root`. The worker relocates inputs to `processed_root` or `failed_root` atomically (rename) after writeback.
- Segment JSON files (if large) MAY be cached on disk with references stored in `extraction_metadata.segment_cache_path`. Retention defaults: processed files kept 30 days, failed 14 days; values override-able via profile knobs (`documents.retention_days.processed|failed`).

**Error & Retry Semantics:**
- Canonical error codes: `unsupported_format`, `password_protected`, `ocr_timeout`, `ocr_language_missing`, `doc_corrupted`, `internal_error`. Retryable: `ocr_timeout`, `ocr_language_missing` (once profile updated), INF-04 rate limits (when hybrid LLM clean-up used). Non-retryable errors MUST set `retryable=false` in job result so INF-02 dead-letters immediately.
- Workers emit structured INF-03 logs with severity `warning` for recoverable retries and `error` for terminal failures, always including `entry_id`, `correlation_id`, `source_path`, and `fingerprint`.

**Timing / SLA Expectations:**
- Target ≤ 400 ms per PDF page (text-based) and ≤ 1.5 s per OCR page on ShapeA hardware. Maximum wall-clock per job: 4 minutes or `page_count * 2 s`, whichever is greater. Workers MUST heartbeat via INF-02 progress events every 30 seconds when processing long files to avoid watchdog cancellation.
- After three failed attempts, the job is routed to the `extraction_dead_letter` queue and EF-06 is marked `failed` with `pipeline_detail` referencing the DLQ ID.

**Downstream Notifications & Logging:**
- On success, enqueue EF-04 job `echo.normalize_entry` with payload `{entry_id, source:'document_extraction', chunk_count=len(extraction_segments), content_lang}` and append an INF-03 `extraction_completed` event (duration, page_count, converter, ocr_used flag).
- On failure, emit `extraction_failed` and optionally `extraction_file_rolled` when moving the document to the failed root. ETS requires recordings of both events for audit trails.

**Testing / ETS Hooks:**
- ETS-Pipeline suite must include fixtures for: text-only PDF (multi-page), scanned PDF requiring OCR, docx with embedded images, and large plaintext (>250k chars). Each fixture verifies EF-06 writes, state transitions, file relocation, and INF-03 logs.
- CI unit tests MUST cover parser selection logic, truncated outputs, and error taxonomy translation; integration smoke test ensures a full job produces a follow-on normalization enqueue.

---

### M02-T04 — Implement EF-03 Document Extraction Worker

- **Type:** implementation  
- **Depends On:** M02-T03  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Segment caching + DOCX/PDF/OCR tests are in; inline truncation + `documents.max_inline_chars` safeguard EF-06 payloads.  

**Description:**  
Implement document extraction using selected libraries/tools. Populate `extracted_text` in EF-06 and update pipeline state.

---

### M02-T05 — Define EF-04 Normalization Rules

- **Type:** design  
- **Depends On:** M02-T01, M02-T03  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Spec locked in `project_scope/tactical/EF04_NormalizationService_Spec_v1.0.md` (job contract, rules, states, ETS gates).  

**Description:**  
Define text cleaning, punctuation normalization, paragraph stitching, whitespace collapse, and safety transformations.

---

### M02-T06 — Implement EF-04 Normalization Worker

- **Type:** implementation  
- **Depends On:** M02-T05  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** EF-04 worker, config defaults, and EF-06 gateway/test coverage implemented; verified via `pytest tests/unit/test_entrystore_gateway.py tests/unit/test_extraction_worker.py tests/unit/test_transcription_worker.py tests/unit/test_normalization_worker.py`.  

**Description:**  
Implement the asynchronous normalization job that produces `normalized_text` fields in EF-06.

---

### M02-T07 — Implement LLM Gateway Integration for EF-05 Semantics

- **Type:** implementation / wiring  
- **Depends On:** INF-04 readiness  
- **ETS Profiles:** ETS-LLM  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
    - **Notes:** INF-04 gateway now returns structured JSON (summary/title/tags/classification), EF-06 persists semantic tags/class labels w/ capture events, and tests/ETS notes cover semantic worker + gateway adapters.  

**Description:**  
Ensure EF-05 calls the LLM Gateway using stable, spec-defined prompts, returns structured outputs (summary, tags, domain/type inferences if allowed), and handles errors gracefully.

Subtasks: 
- ✅ Review EF05_GptEntrySemanticService_Spec_v1.0.md, INF04_LlmGateway_Spec_v1.0.md, and the EF-06 spec to confirm the semantic job contract, required fields, and error taxonomy.
- ✅ Inventory the existing EF-05/semantic worker module (and any INF-04 client stubs) to see what wiring already exists; document required payload schema for the echo.semantic_enrich jobs that normalization now enqueues.
  - ✅ Flesh out generate_semantic_response (and likely additional helper functions) so INF-04 can accept structured prompt specs, route to the configured echo_summary_v1 / echo_classify_v1 profiles, and return JSON summaries/classifications per EF-05 §3–4.
  - ✅ Replace the semantic_worker scaffold with real logic: load the Entry via EF-06, decide summary mode (auto/preview/deep per spec thresholds), call the new INF-04 method, persist summary/title/model provenance, and log capture events. Add classification hooks if the job schema eventually needs them.
  - ✅ Extend the job payload (if required) only after coordinating with EF-05 spec—currently, everything needed is obtainable from EF-06, so no immediate schema change is mandatory. - **_Not Needed_**
- ✅ Implement the LLM Gateway call path: prompt selection, payload mapping, structured response parsing (summary, tags, domain/type), and retry/backoff handling that respects INF-04 error classes.
- ✅ Update EF-06 gateway methods to persist semantic outputs and pipeline states, ensuring capture events/logging mirror EF-02/03/04 patterns.
- ✅ Add targeted unit tests (semantic worker + gateway adapters) plus ETS notes verifying end-to-end LLM requests using mock INF-04 responses.

---

### M02-T08 — Define EF-05 Semantic Operation Contract

- **Type:** design  
- **Depends On:** EF-05 spec  
- **ETS Profiles:** ETS-LLM  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-08 — GPT-5.1-Codex  
  - **Notes:** Contract finalized + published (payload/response schema, EF-06 writes, failure taxonomy) in EF05 spec + status log; ETS hooks defined.

**Description:**  
Specify valid semantic operations (`summarize` v1.0), option fields, expected JSON return structure, and EF-06 update rules.

**Contract Outline (Draft — 2025-12-08):**
- **Job Type:** `echo.semantic_enrich` (INF-02) sourced exclusively from EF-04 completions; `operation` defaults to `summarize_v1` but accepts `classify_v1` when only taxonomy updates are needed.
- **Request Payload Fields:**
  - `entry_id` *(UUID, required)* — EF-06 record to enrich.
  - `operation` *(enum: `summarize_v1`, `classify_v1`)* — drives prompt templates in INF-04.
  - `mode` *(enum: `auto`, `preview`, `deep`)* — summary depth; `auto` respects `summary.max_deep_chars` + `summary.max_preview_chars` from INF-01.
  - `source` *(enum: `normalization`)* — provenance for capture metadata; reserved for future sources.
  - `content_lang` *(ISO 639-1, optional)* — hints LLM + EF-06 `content_lang` overrule.
  - `user_hint` *(string, optional)* — appended to `PromptSpec.user_hint` for reruns.
  - `classification_hint` *(string, optional)* — human-provided note when forcing `classify_v1`.
  - `model_override` *(provider:model, optional)* — forwarded to INF-04 for explicit routing.
  - `correlation_id`, `retry_count`, `ingest_fingerprint` — pass-through telemetry for INF-03 + ETS traceability.
- **Response JSON (shared by all operations):**
  ```json
  {
    "summary": "<2-5 sentences>",
    "display_title": "<<=120 chars>",
    "tags": ["alpha", "beta"],
    "type_label": "ArchitectureNote",
    "domain_label": "Engineering",
    "model_used": "openai:gpt-4o-mini",
    "confidence": {
      "summary": 0.82,
      "classification": 0.74
    }
  }
  ```
  `classify_v1` may omit `summary`/`display_title`; workers treat missing fields as "no-op" for that property while still persisting tags/classifications.
- **EF-06 Persistence Rules:**
  - `summary`, `display_title`, `summary_model`, `semantic_tags` update whenever `summary` payload present.
  - `type_label`, `domain_label`, `classification_model`, `classification_confidence` update when labels exist; capture metadata also records `semantics.{mode,operation,model_used,attempts,tags}`.
  - Every run appends capture events `semantic_started`/`semantic_completed` with `operation`, `mode`, `model`, `processing_ms`, and `retry_count` to keep parity with EF-02/03/04 traces.
- **Failure Taxonomy / Retry Semantics:**
  - INF-04 canonical error codes adopted: `llm_timeout` *(retryable)*, `llm_rate_limited` *(retryable)*, `provider_unavailable` *(retryable)*, `semantic_prompt_empty` *(non-retryable)*, `semantic_response_invalid_json` *(non-retryable)*, plus `internal_error` fallback.
  - EF-05 workers treat retryable errors via exponential backoff (250 ms base, 2x) with max attempts from INF-01 `summary.max_retry_attempts`; non-retryable errors end the job and set EF-06 `last_error.stage = semantics`.
- **Examples & ETS Hooks:** ETS will exercise (1) `summarize_v1` auto mode for <6k char entries, (2) forced `preview` for >6k char entries, and (3) `classify_v1` rerun to validate label-only updates without rewriting summaries.

Subtasks:
- [x] Reconcile EF05_GptEntrySemanticService_Spec_v1.0 with INF04 contract addendum to list supported operations (summarize/classify) plus required inputs.
- [x] Define request payload schema (modes, content thresholds, optional hints) and response JSON (summary/title/tags/classification) with strict typing + examples.
- [x] Map EF-06 persistence requirements (which fields update, capture metadata shape, audit events) for each operation mode.
- [x] Capture failure taxonomy + retry semantics (INF-04 error classes vs EF-05 worker behavior) to unblock ETS planning.
- [x] Publish the contract draft references (spec section, milestone notes, ETS guidance) for downstream tasks T09–T11.

---

### M02-T09 — Implement EF-05 Semantic Worker

- **Type:** implementation  
- **Depends On:** M02-T07, M02-T08  
- **ETS Profiles:** ETS-LLM, ETS-Pipeline  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-08 — GPT-5.1-Codex  
    - **Notes:** Semantic worker logging/tests + ETS README updates landed; contract-compliant payload handling and telemetry are complete (remaining ideas tracked under MI99-T11).  

**Description:**  
Implement worker that performs semantic operations from queued jobs, updates EF-06 `semantic_summary` and `semantic_tags`, and logs all decisions.

Subtasks:
- [x] Add/extend unit tests for semantic worker + LLM gateway to cover summarize_v1 auto/preview modes, classify_v1-only runs, and retry/backoff flows.
- [x] Update `backend/app/jobs/semantic_worker.py` to consume the finalized `echo.semantic_enrich` payload (operation, mode, hints, overrides) and call INF-04 accordingly.
- [x] Ensure EF-06 gateway writes (summary/title/tags/classification, capture metadata, capture events) match the new contract fields, including model provenance + confidence slots.
- [x] Refresh ETS documentation (`tests/README.md`) with the three semantic scenarios defined in the contract.
- [x] Integrate semantic job telemetry into INF-03 logging (structured events + error taxonomy) for MG06 traceability.

---

### M02-T10 — Implement Pipeline Status Transitions in EF-06

- **Type:** implementation  
- **Depends On:** All upstream components  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-08 — GPT-5.1-Codex  
  - **Notes:** EF-06 helper + worker refactors landed; unit/marker sweeps green and documentation updated.  

**Description:**  
Implement robust state transitions:  
`captured → queued → processing → processed`  
`failed` for any terminal error.

Subtasks:
- [x] Extend unit tests (gateway + each worker) to cover valid/invalid transitions, ensuring retries/terminal failures land in the correct states.
- [x] Define the authoritative pipeline state diagram + transition rules (EF-06 spec addendum + shared helper constants) covering ingest_state and pipeline_status pairs.
- [x] Update the EF-06 gateway/state helpers so only valid transitions persist, emitting capture events + audit metadata on every state change.
- [x] Refactor EF-02/03/04/05 workers to use the centralized transition helpers for start/success/failure paths, replacing ad-hoc status writes.
- [x] Refresh ETS documentation/status logs outlining the enforced transitions and how to validate them during pipeline dry runs.

---

### M02-T11 — Implement Pipeline Logging Across Components (INF-03)

- **Type:** implementation  
- **Depends On:** M02-T02 through M02-T09  
- **ETS Profiles:** ETS-Pipeline, ETS-Logging  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-08 — GPT-5.1-Codex  
  - **Notes:** Structured logging helper/tests plus EF-02→EF-05 instrumentation landed; docs/status log refreshed with validation steps.  

**Description:**  
Ensure traceability across EF-02/03/04/05 by logging each transition and error code.

Subtasks:
- [x] Inventory existing logging/capture-event coverage and confirm INF-03 schema requirements for EF-02→EF-05 (analysis/research).
- [x] Draft or enhance unit/ets tests that assert structured logging for start/success/failure paths before touching worker code.
- [x] Implement/update worker logging to satisfy the new tests (transcription, extraction, normalization, semantic) while keeping EF-06 capture metadata aligned.
- [x] Document logging expectations in ETS guidance/status logs, including how to validate them during pipeline dry runs.

---

### M02-T12 — Define/Implement ETS Test Cases for Pipeline

- **Type:** test  
- **Depends On:** All pipeline components  
- **ETS Profiles:** ETS-Pipeline, ETS-LLM  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-09 — GPT-5.1-Codex  
  - **Notes:** Harness, rehearsal procedure, fixtures, and governance logs are complete; ready for ETS operators.  

**Description:**  
Test the full pipeline for:  
- Correct job chaining  
- Error propagation  
- Semantic output correctness  
- State transitions  
- Idempotent re-runs  

Subtasks:
- [x] Draft an ETS pipeline test matrix that enumerates end-to-end scenarios (happy path, retryable/transient faults, terminal failures, semantic-only reruns) referencing the authoritative specs.
- [x] Prepare deterministic ETS fixtures (audio clips, document bundles, normalized payload snapshots) and INF-02 queue seeds so each scenario can be executed repeatedly across Runtime Shapes A/B.
- [x] Implement or extend the automated ETS harness/marker sweep (pytest + orchestration scripts) that runs EF-02→EF-05 jobs, captures telemetry, and asserts pipeline statuses/logging for success/failure paths.
- [x] Document the rehearsal procedure in `tests/README.md` (or dedicated ETS guide) outlining command sequences, expected artifacts, and verification steps for operators before milestone sign-off.
- [x] Add a status log entry summarizing the ETS pipeline test coverage, execution results, and any open issues or observations for future improvements.
- [x] Promote the M02-T12 task to `done` once all tests pass consistently and documentation is finalized.
- [x] Generate a git commit.

---

### M02-T13 — Produce Status Log for M02

- **Type:** governance  
- **Depends On:** Initial pipeline mechanics  
- **Status Block:**
  - **Status:** done 
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Create structured status logs reflecting milestone progress per MTS v1.1.

---

### M02-T14 — Capture Architectural Decisions for M02

- **Type:** governance  
- **Depends On:** M02-T01 through M02-T12  
- **Status Block:**  
  - **Status:** done  
  - **Last Updated:** 2025-12-09 — GPT-5.1-Codex  
  - **Notes:** Decisions logged in `pm/decisions/2025-12-09_ef03_extraction_toolchain.md`, `..._ef04_normalization_profiles.md`, and `..._ef05_semantic_prompt_stack.md`.  

**Description:**  
Record decisions around LLM model selection, extraction tools, normalization strategy, and semantic prompt design.

---

## 4. Exit Criteria

M02 is complete when:

1. EF-02/03/04/05 workers reliably process all pipeline job types.  
2. EF-06 contains properly updated fields reflecting each stage.  
3. Jobs flow through INF-02 with correct payloads.  
4. Logging provides timeline reconstruction.  
5. ETS test suite validates the end-to-end flow.  
6. Status logs and decisions recorded under `pm/`.

