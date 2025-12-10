# Decision: EF-03 Extraction Toolchain + Artifact Policy (2025-12-09)

## Context
- Milestone: M02 — Processing Pipeline
- Trigger: EF-03 worker is finalized (`backend/app/jobs/extraction_worker.py`) and needs a durable record of the chosen libraries, artifact layout, and retry semantics.
- Signals: ETS harness plus `tests/unit/test_extraction_worker.py` now rely on deterministic behavior from `backend/app/domain/ef03_extraction/service.py`, including PDF/page chunking and segment caching heuristics.

## Decision
1. **Library stack** — Use `pdfminer.six` for PDFs, `python-docx` for DOCX, and UTF-8 text streaming for `.txt/.md/.rtf`. OCR remains out-of-scope; when PDFs lack text we raise `ocr_required` (retryable unless `ocr_mode=off`).
2. **Segmentation strategy** — Plain text/docx chunks split on paragraph boundaries; PDFs rely on form-feed page splits. Each segment records `index`, `label`, `char_count`, and `text` to give EF-04 predictable chunk metadata.
3. **Artifact handling** — Always write the full extraction output to disk under `documents.extraction_output_root` with a stable `<entry_id>.txt` naming pattern. Inline EF-06 payloads are trimmed via `documents.max_inline_chars`, with truncation details captured in metadata.
4. **Segment cache** — When serialized segments exceed `segment_cache_threshold_bytes`, persist them under `segment_cache_root` and store only the reference path + byte length in EF-06 metadata. This keeps database rows lean while allowing ETS to verify disk artifacts.
5. **State + job chaining** — On success, enqueue `echo.normalize_entry` with `{entry_id, source:'document_extraction', chunk_count, content_lang}` to keep M02 transitions deterministic. Failures move source files to `documents.failed_root` and emit `extraction_failed` capture events with retry flags.

## Rationale
- Aligns exactly with EF06 spec addendum on payload sizing and file retention, avoiding oversized `extracted_text` writes.
- Libraries above are already vendored/tested; swapping them would invalidate ETS fixtures and increase schedule risk.
- Segment caching lets us support large PDFs (200+ pages) without inflating Postgres rows, while still enabling downstream analytics by loading from disk.
- Explicit job chaining + capture events keep INF-02 telemetry consistent with the EF-02/04/05 workers and satisfy MG06 logging requirements.

## Follow-Ups
1. Document the extraction knobs (`documents.*`) in config README / INF-01 spec so operators know which directories to pre-create per runtime shape.
2. When OCR support is added, extend this decision (or create an addendum) describing the chosen OCR library and how it plugs into the existing error taxonomy.
3. Reference this memo in M02-T14 status notes once the task is marked `done`.
