# Decision: EF-06 Capture Fingerprint Columns (2025-12-07)

## Context
- Milestone: M01 — Capture & Ingress (tasks M01-T01/T02/T04/T06).
- Specs referenced: `EF01_CaptureService_Interfaces_Spec_v1.1.md`, `EF06_EntryStore_Spec_v1.1.md`, `EF06_EntryStore_Addendum_v1.2.md`.
- EF-01 watcher + API capture paths now compute fingerprints and rely on EF-06 for idempotency, but the current `entries` schema lacks first-class fields for storing those fingerprints.

## Options Considered
1. **Continue storing fingerprints only in EF-01 memory/tests** — keep schema unchanged and rely on transient comparisons.
2. **Add a separate `capture_attempts` table** — normalize capture attempts outside `entries` and join during ingest.
3. **Extend `entries` with dedicated fingerprint columns** — add `capture_fingerprint` (text) and `fingerprint_algo` (text/enum) plus optional JSON metadata, aligning with existing Entry records.

## Decision
Extend the `entries` table with:
- `capture_fingerprint TEXT NOT NULL` (or nullable until migrations run) representing the deterministic hash EF-01 computes.
- `fingerprint_algo TEXT NOT NULL` capturing the hashing recipe (e.g., `sha256:path+size`).
- Optional `capture_metadata JSONB` for watcher-specific context (root id, move history).

These columns become mandatory for EF-01-created entries once migrations run. They unblock the composite index defined in `2025-12-06_ingestion_indexes.md` and keep the idempotency contract entirely within EF-06.

## Rationale
- Keeps EF-01 ↔ EF-06 contract self-contained; no auxiliary tables needed for M01 scope.
- Enables deterministic duplicate detection for watcher, manual, and `/api/capture` flows using a single record lookup.
- Aligns with EF06 addendum guidance to extend the `entries` schema before inventing new stores.
- Simplifies ETS validation because tests can assert against persisted fingerprint columns via the gateway adapter once Postgres is wired in.

## Follow-Ups
1. Author a Postgres migration introducing the new columns with default values/backfill strategy.
2. Update EF-06 spec + addendum to document the fields and their constraints.
3. Modify EF-01 gateways so watcher/manual/API paths always populate these fields, and ensure `/tests` cover persistence once the DB adapter lands.
4. Reference this decision when implementing the `IDX_entries_fingerprint_channel` unique index.

## Notes for Reviewers
- Adding columns now avoids refactoring EF-01 logic later and keeps milestone scope bounded.
- If future milestones introduce a dedicated capture-attempts ledger, this decision can be revisited, but EF-06 must continue surfacing fingerprint data in its primary record shape.
