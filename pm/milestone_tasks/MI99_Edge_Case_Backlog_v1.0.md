# MI99 — Edge-Case & Decision Follow-Ups — v1.0

---

## 0. Metadata

- **Milestone ID:** MI99  
- **Milestone Name:** Edge-Case & Decision Follow-Ups  
- **Scope Summary:**  
  Track out-of-band tasks that fall outside the standard M01–M07/MG0x milestones but still require execution or monitoring. Initial focus: follow-ups from the ingestion-index decision (`pm/decisions/2025-12-06_ingestion_indexes.md`).  
- **Primary Components:**  
  - EF-06 EntryStore schema + metadata  
  - EF-01 CaptureService wiring  
  - EF-07 API capture contracts  
  - ETS validation coverage  
- **Related Artifacts:**  
  - `pm/decisions/2025-12-06_ingestion_indexes.md`  
  - `EF06_EntryStore_Spec_v1.1.md` + addendum  
  - `EF01_CaptureService_Interfaces_Spec_v1.1.md`  
  - `EF07_Api_Contract_v1.2.md`  

---

## 1. Status Tracking Guidance

Same field semantics as core milestones, but MI99 may be updated opportunistically as edge-cases emerge.

- **Status values:** `pending`, `in_progress`, `blocked`, `deferred`, `done`.  
- Update only the Status Block for each task when recording progress.  

Template:

```markdown
- **Status:** pending
- **Last Updated:** —
- **Notes:** —
```

---

## 2. Tasks

### MI99-T01 — Add Fingerprint Columns to `entries`

- **Type:** schema  
- **Depends On:** Decision MI99-D01 (ingestion indexes)  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** `backend/migrations/versions/20251207_add_capture_fingerprint_columns.py` adds the columns + supporting indexes per MI99-D01.  

**Description:**  
Extend EF-06 `entries` schema with `capture_fingerprint` (text) and `fingerprint_algo` (enum/text per EF06 addendum). Ensure migrations/spec updates reflect nullable/default behavior needed for backfill.

---

### MI99-T02 — Write Fingerprint Metadata from EF-01

- **Type:** implementation  
- **Depends On:** MI99-T01  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Watcher/manual/API capture paths now call `EntryStoreGateway.create_entry` with `capture_fingerprint` + `fingerprint_algo` metadata (see `backend/app/domain/ef01_capture/*.py`, `backend/app/api/routers/capture.py`).  

**Description:**  
Update EF-01 ingestion paths (watch folders, manual text, API `file_ref`) to compute fingerprints and persist both fingerprint and algorithm when creating entries.

---

### MI99-T03 — Document Indexes in EF06 Spec

- **Type:** documentation  
- **Depends On:** MI99-T01  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** `project_scope/tactical/EF06_EntryStore_Spec_v1.1.md` now lists the fingerprint/source-path indexes with a reference to decision `2025-12-06_ingestion_indexes.md`.  

**Description:**  
Amend `EF06_EntryStore_Spec_v1.1.md` (or next rev) to list `IDX_entries_fingerprint_channel`, `IDX_entries_source_channel`, and `IDX_entries_source_path`, referencing decision MI99-D01.

---

### MI99-T04 — Validate Idempotency via ETS Profiles

- **Type:** testing  
- **Depends On:** MI99-T02, MI99-T03  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Blocking on new ETS coverage that exercises EF-01 watcher/API flows against the Postgres gateway once MI02 Postgres adapter is stable.  

**Description:**  
Expand ETS profiles (EF01-WATCH, EF01-API) to prove the new indexes prevent duplicate entries and keep query plans efficient for replay scenarios.

---

### MI99-T05 — Define Transcript Retention & Cleanup Policy

- **Type:** governance/process  
- **Depends On:** M02-T02b transcript externalization (decision `2025-12-07_m02_t02b_transcript_externalization.md`)  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** New task; needs policy + automation design.  

**Description:**  
Codify how EF-02 transcript artifacts under `llm.whisper.transcript_output_root` are retained, rotated, or deleted so desktop installs do not grow unbounded. Deliverables: retention policy doc (linkable from EF06/INF01 specs), cleanup script or service hook tied to entry archival, and ETS guidance for verifying the process.

---

### MI99-T06 — Surface Whisper Configuration in EF-07 UI

- **Type:** UX follow-up  
- **Depends On:** M05 UI scaffolding, INF-01 charter for Whisper config  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Track requirement ahead of M05 so EF-07 desktop UI exposes Whisper enablement + transcript root.  

**Description:**  
Expose current Whisper/transcript settings inside the EF-07 desktop UI so operators can verify model/device, transcript output roots, and public URL mappings without leaving the app. This should land alongside the broader settings shell built in M05; document the UX intent here so it is not deferred post-M05.

### MI99-T07 — Whisper GPU vs CPU Deployment Guidance

- **Type:** documentation / ops  
- **Depends On:** M02-T02a (Whisper integration), INF-01 config loader  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Need install/runbooks covering CUDA/cuDNN requirements for GPU nodes plus CPU-only fallback instructions.

**Description:**  
Produce an install note (MI99) that distinguishes GPU-capable deployments (CUDA + cuDNN pre-reqs, `ECHOFORGE_WHISPER_DEVICE=cuda`) from CPU-only environments (`device=cpu`, smaller models). Include dependency lists, verification steps, and guidance for operators selecting the correct profile so EF-02 transcription does not silently fall back to the stub.

### MI99-T08 — Whisper Segment Artifact Strategy

- **Type:** decision placeholder  
- **Depends On:** EF-04 chunking plan, M02-T02b transcript externalization  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Defer choice until EF-04 normalization needs clear guidance on segment access.

**Description:**  
Evaluate two approaches for handling EF-02 `.segments.json` artifacts now that Whisper emits them by default: (1) add an INF-01 flag `llm.whisper.persist_segments` so deployments can skip writing the file entirely and rely solely on EF-06 `transcription_segments`, or (2) keep writing the file but define a retention/cleanup policy aligned with transcript lifecycles (delete after N days or post-normalization). Decision should be revisited alongside EF-04 implementation so downstream consumers dictate whether local segment caching is worth the storage overhead.

### MI99-T09 — Verbatim Preview Fallback for Long Entries

- **Type:** decision/documentation  
- **Depends On:** EF-02, EF-03, EF-05 pipeline planning  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Capture rule that `verbatim_preview` must always contain either the full text (short entries), a truncated slice with ellipsis, or the EF-05 summary.

**Description:**  
Ensure every entry presents something meaningful even if EF-05 hasn’t produced a summary yet. For short documents/transcripts, `verbatim_preview` mirrors the entire text. For longer ones, EF-02/EF-03 should write the full verbatim file to disk and store a truncated preview (with ellipsis) until EF-05 overwrites it with a summary. This prevents NULL/empty previews and keeps the UI/API consistent across ingestion types.

---

### MI99-T10 — Define EF-03 OCR Fallback Strategy

- **Type:** decision / implementation placeholder  
- **Depends On:** M02-T04 EF-03 worker readiness, OCR tooling selection (e.g., Tesseract bindings)  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Tracks the OCR fallback plan requested during M02-T04; blocked here until tooling is decided.  

**Description:**  
Document and implement the OCR path EF-03 should take when pdfminer detects image-only pages. Tasks include: choosing the OCR engine (likely Tesseract), defining INF-01 knobs (language packs, timeout), specifying error taxonomy interactions (`ocr_required`, `ocr_timeout`), and outlining ETS fixtures for scanned PDFs. Once decisions are captured here, M02-T04 can pull the finalized approach back into the worker.

---

### MI99-T11 — EF-05 Semantic Enhancements (Nice-to-have)

- **Type:** implementation / telemetry polish  
- **Depends On:** M02-T09 semantic worker rollout  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-08 — GPT-5.1-Codex  
  - **Notes:** Nice-to-have backlog item captured per 2025-12-08 discussion; not blocking M02 delivery.  

**Description:**  
Optional follow-ups for the EF-05 semantic worker once the must-do features are stable:

1. Inject canonical `type_labels` / `domain_labels` vocab lists into the `classify_v1` prompt and surface suggested labels without persisting them automatically.  
2. Extend INF-04 response handling to persist summary/classification confidence values into dedicated EF-06 columns (or capture metadata until schema lands).  
3. Wire additional INF-04 routing hints (temperature overrides, user model overrides) so operators can steer semantic runs without code changes.  

These refinements improve long-term usability but are explicitly marked **Nice-to-have** so they can be scheduled after the current milestone cut. 

---

## 3. Adding Future Edge-Case Tasks

New edge items can be appended as `MI99-T0x` entries with the same Status Block structure. Reference any upstream decision or spec change so the history of why the item exists remains clear.
