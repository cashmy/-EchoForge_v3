# Decision: EF-04 Normalization Profiles & Rule Stack (2025-12-09)

## Context
- Milestone: M02 — Processing Pipeline
- Trigger: `backend/app/jobs/normalization_worker.py` now enforces configurable rule profiles and streams jobs directly into semantics; we need to memorialize the chosen defaults.
- Signals: ETS rehearsal procedure plus unit coverage lean on deterministic rule ordering (`strip_controls`, `normalize_lists`, etc.) and the shared capture-metadata schema.

## Decision
1. **Profile model** — Keep normalization settings in `echo.normalization` with a `default_profile` of `standard`. Profiles inherit from base settings and can be overridden per job via `normalization_profile` or inline `overrides` payload keys.
2. **Rule ordering** — Always execute in this sequence: strip control chars/BOM, normalize newlines, replace smart quotes, remove timestamps & speaker labels (when enabled), collapse whitespace, normalize bullet lists, then optional sentence-case for all-caps text. Rules record timing + applied flags for auditability.
3. **Safety limits** — Enforce `max_input_chars` and `max_output_chars` per profile, marking truncation metadata when limits are hit. Fail fast with `normalization_no_content` when the cleaned text empties.
4. **Capture + logging** — Every job emits `normalization_started/completed/failed` capture events and patches `capture_metadata.normalization` with char counts, segment totals, and profile name. Failures append `last_error.stage='normalization'` to EF-06 for postmortems.
5. **Job chaining** — Upon success, enqueue `echo.semantic_enrich` with the detected `content_lang`, resolved segment count, and correlation ID, ensuring semantics always run against normalized text.

## Rationale
- Profile inheritance lets operators tune future runtime shapes (e.g., aggressive timestamp removal for audio vs. doc flows) without code changes.
- Fixed rule ordering guarantees ETS reproducibility and simplifies debugging when normalization output diverges from expectations.
- Truncation safeguards prevent oversized EF-06 payloads and match the storage rules captured in EF06 addendum §4.
- Consistent capture metadata keeps MG06 logging/traceability requirements satisfied and aligns with EF-02/03/05 workers.

## Follow-Ups
1. Extend `tests/README.md` with guidance on swapping profiles during ETS dry runs (e.g., `pytest -k normalization --normalization-profile dense_notes`).
2. If future profiles introduce regex-heavy steps or language-specific casing rules, capture an addendum referencing this decision.
3. Cross-link this memo from M02-T14 notes once the task flips to `done`.
