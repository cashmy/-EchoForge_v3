# EchoForge Milestone Summary — v1.2
## Updated for Runtime Shapes, EF‑07.1 Desktop Host Adapter, ETS Governance, and Full v3 Architecture

---

# 0. Metadata

- **Artifact:** EchoForge_Milestone_Summary_v1.2  
- **Status:** Planning (Updated)  
- **Purpose:** Canonical roadmap for EchoForge v3 architecture  
- **Supersedes:** v1.1  
- **Primary Changes:**  
  - Incorporates Runtime Shapes (A/B/C)  
  - Adds EF‑07.1 Desktop Host Adapter milestone  
  - Clarifies EF‑07 SPA responsibilities  
  - Re‑aligns ingestion phases (EF‑01 → EF‑04)  
  - Adds ETS (EnaC Testing Subsystem) milestones  
  - Improves phase sequencing and inter‑component dependencies  

---

# 1. Guiding Architectural Principles

EchoForge v3 development follows:

- **Runtime Shape governance**  
  A (browser dev), B (Electron desktop), C (future SaaS).

- **Strict component boundaries**  
  EF‑01 (Capture), EF‑02 (Transcription), EF‑03 (Extraction), EF‑04 (Normalization),  
  EF‑05 (Entry Semantics), EF‑06 (EntryStore), EF‑07 (API/UI), EF‑07.1 (Desktop Host Adapter), EF‑08 (Integration Boundary).

- **Single‑Entry semantic constraint**  
  No cross‑Entry or multi‑Entry reasoning (per Scope & Boundaries v1.1).

- **ETS governance**  
  Test‑first, profile‑driven, module locking, and drift‑prevention.

- **Local‑first deployment**  
  Electron desktop runtime (Shape B) is primary for v3 free tier.

---

# 2. Phase Overview

```
Phase 0 — Foundation & Repository Structure  
Phase 1 — EF‑01 CaptureService  
Phase 2 — EF‑02 / EF‑03 / EF‑04 Ingestion & Normalization  
Phase 3 — EF‑05 Single‑Entry Semantics  
Phase 4 — EF‑06 EntryStore & Persistence  
Phase 5 — EF‑07 API, SPA, and EF‑07.1 Desktop Host Adapter  
Phase 6 — ETS Integration, Hardening, and Runtime QA  
Phase 7 — Packaging, Distribution, and v3 Release  
```

---

# 3. Phase 0 — Project Foundation

### Milestone 0.1 — Repository & Structure

- Establish repo with `/src`, `/pm`, `/pm/milestones`, `/pm/decisions`, `/pm/status_logs`.
- Include Architecture Overview v1.1, Component Summary, Runtime Shapes Spec v1.0.
- Add ETS v1.0 as governance layer documentation.
- Define dev profiles for runtime shapes A (browser) & B (desktop).

**Acceptance Criteria**

- Repository compiles.
- Tests run (empty ETS profile OK).
- Electron + Python backend skeleton directories created (no logic required).

---

# 4. Phase 1 — EF‑01 CaptureService (Watcher & Input Routing)

### Milestone 1.1 — Watcher Integration

- Watch folder for audio/doc drops.
- On file detection:  
  - Register new Entry in EF‑06.  
  - Populate `source_type`, `source_channel`, `source_path`.

### Milestone 1.2 — Manual Entry & API Entry

- UI submission routed to EF‑01.
- API ingest endpoint (Shape A/B compatible).

### Milestone 1.3 — JobQueue Integration (INF‑02)

- Submit transcription/extraction jobs to queue.

**Acceptance Criteria**

- Files dropped into watch folder appear as “raw” entries.
- Entries reach EF‑02 via queued job.

---

# 5. Phase 2 — EF‑02 TranscriptionService / EF‑03 Extractor / EF‑04 Normalization

### Milestone 2.1 — EF‑02 Transcription

- Integrate STT provider (Whisper or other).
- Normalize audio → text segments.

### Milestone 2.2 — EF‑03 Extraction

- Extract document text from PDF/DOCX.
- Populate `raw_text`, `length`, `mime_type`.

### Milestone 2.3 — EF‑04 Normalization

- Clean whitespace, timestamps, floats, artifacts.
- Produce `normalized_text` for EF‑05.

**Acceptance Criteria**

- Any ingest path resolves to normalized text.
- ETS per-module profiles pass:
  - EF‑02‑P  
  - EF‑03‑P  
  - EF‑04‑P  

---

# 6. Phase 3 — EF‑05 Single‑Entry Semantic Processing

### Milestone 3.1 — Entry Semantic Service (EF‑05)

- Classify Entry type (meeting? note? conversation?).
- Provide summary.
- Provide structured metadata.
- Provide optional refinements (as permitted by v3 boundaries).

### Milestone 3.2 — Logging & Metrics (INF‑03)

- Apply request ID, latency reporting, ingestion timing.

**Acceptance Criteria**

- EF‑05 returns deterministic output per Entry.
- No cross‑Entry operations allowed (ETS guard rule EF‑05‑G).

---

# 7. Phase 4 — EF‑06 EntryStore

### Milestone 4.1 — PostgreSQL Schema

- Implement full schema:
  - Entry metadata  
  - Content blobs  
  - Source channels  
  - Semantics  
  - Audit fields

### Milestone 4.2 — Persistence Layer

- CRUD operations with transactional safety.
- Indexing on timestamp, source_channel.

### Milestone 4.3 — Search & Filter (non-semantic)

- Filter by:
  - Date  
  - Source  
  - EntryType (from EF‑05)  

**Acceptance Criteria**

- Store can handle ingestion throughput.
- ETS verifies isolation rules (EF‑06‑I).

---

# 8. Phase 5 — EF‑07 API, SPA, and EF‑07.1 Desktop Host Adapter

## Milestone 5.1 — EF‑07 API (Host‑Agnostic)

- Expose endpoints for:
  - Entry CRUD  
  - Semantic results  
  - UI filtering  
- Conform to Runtime Shapes A/B/C.

## Milestone 5.2 — EF‑07 SPA Shell

- React SPA using Tailwind + MUI (tables only).
- Light/Dark themes.
- SPA must not call Electron APIs directly.

**Acceptance Criteria**

- SPA renders in browser (Shape A).
- SPA displays Entry list and filters.

## Milestone 5.3 — EF‑07.1 Desktop Host Adapter (Electron Shape B)

- Implement Desktop Host Adapter to:
  - Start backend services.  
  - Verify health.  
  - Load SPA in Electron.  
  - Provide minimal IPC surface.  
- Enforce EF‑07.1 non-responsibilities (no domain logic, no DB, no infra).

**Acceptance Criteria**

- Desktop app launches, starts backend, loads SPA.
- SPA works identically in Shape A and Shape B.
- IPC surface limited to `platform.getInfo`, `platform.quit`, `platform.restartBackend`.

## Milestone 5.4 — UI Views

- Dashboard (v1)
- Entry List (MUI grid)
- Entry Detail
- Entry Actions (summaries, metadata lookup)

---

# 9. Phase 6 — ETS Integration, Stability, Runtime QA

## Milestone 6.1 — ETS Harness Activation

- Establish test profiles for:
  - EF‑01–EF‑07  
  - EF‑07.1  
  - INF‑01–INF‑04  

- Lock modules during tests (ETS rule: LM-Lock).

## Milestone 6.2 — Drift Prevention Matrix

- Validate:
  - No SKY/MINT semantics leaked into EF.  
  - No multi-Entry operations.  
  - EF‑07 host-agnostic contract holds.  
  - Runtime Shapes are aligned.

## Milestone 6.3 — Reliability & Stress

- Feed synthetic load through ingestion → EF‑05 → EF‑06 → UI.
- Validate desktop runtime stability.

---

# 10. Phase 7 — Packaging & Release

### Milestone 7.1 — Desktop Bundling

- Electron packager.
- Local PostgreSQL bootstrap.
- Config profiles (user-level, app-level).

### Milestone 7.2 — Installer & Auto-Update (optional)

### Milestone 7.3 — Documentation & Final QA

---

# 11. Changelog

### v1.2 Changes

- Added Runtime Shapes (A/B/C) integration.
- Added EF‑07.1 Desktop Host Adapter milestone.
- Corrected ingestion pipeline alignment (EF‑01 → EF‑04).
- Strengthened EF‑07 SPA host-agnostic rules.
- Introduced Phase 6 ETS governance milestones.
- Re-sequenced UI milestones into Shape-aware structure.
