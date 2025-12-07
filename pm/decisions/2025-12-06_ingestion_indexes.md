# Decision: EF-06 Ingestion Index Strategy (2025-12-06)

## Context
- Milestone: M01 — Capture & Ingress (task M01-T02 "Define Ingestion-Related Indexes / Query Patterns").
- Specs referenced: `EF01_CaptureService_Interfaces_Spec_v1.1.md` (fingerprint + idempotency), `EF06_EntryStore_Spec_v1.1.md` + addendum (entries schema), `EF07_Api_Contract_v1.2.md` (capture flows).
- Need: guarantee EF-01 idempotency by letting CaptureService quickly detect duplicates across watch folders and manual/API sources while preserving lookup speed for operational tooling.

## Options Considered
1. **Unique index on `source_path` alone** — rejected because watch flows can re-use paths (archival replays, re-uploads) and manual/API captures do not always have stable filesystem paths.
2. **Dedicated capture-attempts table with its own indexes** — deferred to a later milestone; adds schema and API surface that are not required to satisfy M01 exit criteria.
3. **Composite index on fingerprint metadata plus supporting channel/path indexes** — chosen; keeps all ingestion lookups inside `entries` while supporting watcher and manual/API scenarios once fingerprint columns are introduced.

## Decision
Implement the following EF-06 indexes as soon as the fingerprint columns land on `entries`:
- `IDX_entries_fingerprint_channel` — unique, covering `(capture_fingerprint, source_channel)`.
- `IDX_entries_source_path` — non-unique, covering `(source_path)`.
- `IDX_entries_source_channel` — non-unique, covering `(source_channel)`.

## Rationale
- `capture_fingerprint + source_channel` is the tightest tuple EF-01 needs for deterministic idempotency across watcher roots, manual text, and API handoffs.
- Separate `source_path` index supports rapid replays from disk without forcing a fingerprint recompute.
- `source_channel` filters underpin manual-text lookups ("show me most recent manual capture") and API-side audits.
- Keeping all three indexes on `entries` avoids a short-term proliferation of capture-tracking tables while aligning with EF06 spec guidance to extend the existing schema first.

## Follow-Ups
1. Add `capture_fingerprint` (text) and `fingerprint_algo` (enum/text) columns to `entries` per EF06 addendum guidance.
2. Ensure EF-01 (M01-T04/T06) writes both fingerprint and source metadata during entry creation.
3. Update EF06 spec file with the new indexes after schema change lands; cross-link this decision for traceability.
4. Validate through ETS profiles (EF01-WATCH/EF01-API) that duplicate submissions are skipped and the indexes are used in query plans.

## Notes for Reviewers
- This decision aligns with the governance directive to capture schema-impacting choices under `pm/decisions/`.
- If future milestones introduce a dedicated capture-attempts log, revisit whether the unique composite should move there instead.
