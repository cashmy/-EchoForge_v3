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
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Specify the exact EF-02 contract: input payload, text result structure, error codes, timing expectations, and EF-06 update requirements (`transcription_text`, `ingest_state` transitions).

---

### M02-T02 — Implement EF-02 Transcription Worker

- **Type:** implementation  
- **Depends On:** M02-T01  
- **ETS Profiles:** ETS-Pipeline, ETS-LLM  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement the worker that consumes a `transcription` job, invokes whisper/LLM STT through INF-04, updates EF-06, and moves files to processed/failed.

---

### M02-T03 — Define EF-03 Document Extraction Input/Output Contract

- **Type:** design  
- **Depends On:** M01  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define EF-03 inputs/outputs for `.pdf`, `.docx`, `.txt`, ensuring extraction results flow into EF-06 and feed EF-04.

---

### M02-T04 — Implement EF-03 Document Extraction Worker

- **Type:** implementation  
- **Depends On:** M02-T03  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement document extraction using selected libraries/tools. Populate `extracted_text` in EF-06 and update pipeline state.

---

### M02-T05 — Define EF-04 Normalization Rules

- **Type:** design  
- **Depends On:** M02-T01, M02-T03  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define text cleaning, punctuation normalization, paragraph stitching, whitespace collapse, and safety transformations.

---

### M02-T06 — Implement EF-04 Normalization Worker

- **Type:** implementation  
- **Depends On:** M02-T05  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement the asynchronous normalization job that produces `normalized_text` fields in EF-06.

---

### M02-T07 — Implement LLM Gateway Integration for EF-05 Semantics

- **Type:** implementation / wiring  
- **Depends On:** INF-04 readiness  
- **ETS Profiles:** ETS-LLM  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Ensure EF-05 calls the LLM Gateway using stable, spec-defined prompts, returns structured outputs (summary, tags, domain/type inferences if allowed), and handles errors gracefully.

---

### M02-T08 — Define EF-05 Semantic Operation Contract

- **Type:** design  
- **Depends On:** EF-05 spec  
- **ETS Profiles:** ETS-LLM  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Specify valid semantic operations (`summarize` v1.0), option fields, expected JSON return structure, and EF-06 update rules.

---

### M02-T09 — Implement EF-05 Semantic Worker

- **Type:** implementation  
- **Depends On:** M02-T07, M02-T08  
- **ETS Profiles:** ETS-LLM, ETS-Pipeline  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement worker that performs semantic operations from queued jobs, updates EF-06 `semantic_summary` and `semantic_tags`, and logs all decisions.

---

### M02-T10 — Implement Pipeline Status Transitions in EF-06

- **Type:** implementation  
- **Depends On:** All upstream components  
- **ETS Profiles:** ETS-Pipeline  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

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
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Ensure traceability across EF-02/03/04/05 by logging each transition and error code.

---

### M02-T12 — Define/Implement ETS Test Cases for Pipeline

- **Type:** test  
- **Depends On:** All pipeline components  
- **ETS Profiles:** ETS-Pipeline, ETS-LLM  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

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
  - **Last Updated:** —  
  - **Notes:** —  

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

