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

## 1. Status Tracking Model  
Each task contains a **Status Block**:

```markdown
- **Status:** pending  <!-- pending | in_progress | blocked | deferred | done -->
- **Last Updated:** —
- **Notes:** —
```

Codex-LLM MUST only edit these three fields.

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
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Define EF-03 inputs/outputs for `.pdf`, `.docx`, `.txt`, ensuring extraction results flow into EF-06 and feed EF-04.

---

### M02-T04 — Implement EF-03 Document Extraction Worker

- **Type:** implementation  
- **Depends On:** M02-T03  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Implement document extraction using selected libraries/tools. Populate `extracted_text` in EF-06 and update pipeline state.

---

### M02-T05 — Define EF-04 Normalization Rules

- **Type:** design  
- **Depends On:** M02-T01, M02-T03  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Define text cleaning, punctuation normalization, paragraph stitching, whitespace collapse, and safety transformations.

---

### M02-T06 — Implement EF-04 Normalization Worker

- **Type:** implementation  
- **Depends On:** M02-T05  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Implement the asynchronous normalization job that produces `normalized_text` fields in EF-06.

---

### M02-T07 — Implement LLM Gateway Integration for EF-05 Semantics

- **Type:** implementation / wiring  
- **Depends On:** INF-04 readiness  
- **ETS Profiles:** ETS-LLM  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Ensure EF-05 calls the LLM Gateway using stable, spec-defined prompts, returns structured outputs (summary, tags, domain/type inferences if allowed), and handles errors gracefully.

---

### M02-T08 — Define EF-05 Semantic Operation Contract

- **Type:** design  
- **Depends On:** EF-05 spec  
- **ETS Profiles:** ETS-LLM  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Specify valid semantic operations (`summarize` v1.0), option fields, expected JSON return structure, and EF-06 update rules.

---

### M02-T09 — Implement EF-05 Semantic Worker

- **Type:** implementation  
- **Depends On:** M02-T07, M02-T08  
- **ETS Profiles:** ETS-LLM, ETS-Pipeline  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Implement worker that performs semantic operations from queued jobs, updates EF-06 `semantic_summary` and `semantic_tags`, and logs all decisions.

---

### M02-T10 — Implement Pipeline Status Transitions in EF-06

- **Type:** implementation  
- **Depends On:** All upstream components  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Implement robust state transitions:  
`captured → queued → processing → processed`  
`failed` for any terminal error.

---

### M02-T11 — Implement Pipeline Logging Across Components (INF-03)

- **Type:** implementation  
- **Depends On:** M02-T02 through M02-T09  
- **ETS Profiles:** ETS-Pipeline, ETS-Logging  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Ensure traceability across EF-02/03/04/05 by logging each transition and error code.

---

### M02-T12 — Define/Implement ETS Test Cases for Pipeline

- **Type:** test  
- **Depends On:** All pipeline components  
- **ETS Profiles:** ETS-Pipeline, ETS-LLM  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Test the full pipeline for:  
- Correct job chaining  
- Error propagation  
- Semantic output correctness  
- State transitions  
- Idempotent re-runs  

---

### M02-T13 — Produce Status Log for M02

- **Type:** governance  
- **Depends On:** Initial pipeline mechanics  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Pending kickoff; awaiting M02 execution window.  

**Description:**  
Create structured status logs reflecting milestone progress per MTS v1.1.

---

### M02-T14 — Capture Architectural Decisions for M02

- **Type:** governance  
- **Depends On:** M02-T01 through M02-T12  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

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

