# M03-T01 — Subtask Plan & Initial Test Matrix

_Date:_ 2025-12-09  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `pm/milestone_tasks/M03_Taxonomy_Classification_Tasks_v1.1.md` scopes EntryType as an advisory taxonomy overlay with optional EF-06 references; it calls for flexible string IDs plus timestamps.
- `tests/unit/test_entrystore_gateway.py` currently provisions only `type_label` / `domain_label` columns (no `type_id`), so downstream workers (`backend/app/jobs/semantic_worker.py`) rely solely on free-form labels—confirming the schema gap we must close before referencing taxonomy tables.
- `backend/app/jobs/semantic_worker.py` already persists `type_label` / `domain_label` metadata; when taxonomy IDs arrive, this worker (and EF-05 spec) will need a deterministic mapping, so the Type table must include stable identifiers + activation flags suitable for LLM hints.

## 2. Proposed Subtasks
1. **ST01 — Schema Definition Addendum:** Author an EF06 spec addendum section that enumerates EntryType columns (`id`, `name`, `label`, `description`, `active`, `sort_order`, `created_at`, `updated_at`, optional `metadata` JSON). Include constraints (PK on `id`, unique `name`, default `active=true`, `sort_order` default 500).
2. **ST02 — Referential Behavior & Soft Delete:** Define how Entries reference Types (`type_id` nullable, not FK), what happens when a Type is deactivated vs deleted, and how UI/API should surface dangling IDs. Document retention of free-form `type_label` for resilience.
3. **ST03 — Migration Blueprint:** Outline the EF-06 migration steps (new `entry_types` table, seed rows optional, migrations for existing environments). Capture expected Alembic/SQL scripts and backfill strategy for historical data (e.g., map common `type_label` values to canonical IDs later).
4. **ST04 — API Contract Alignment:** Map the schema to EF-07 endpoints (`GET/POST/PATCH/DELETE /api/types`). Specify validation rules, payload shapes, and how `active`/`sort_order` interplay with UI dropdowns.
5. **ST05 — Governance & Observability:** Decide logging/metadata expectations (`capture_events` when `type_id` changes) and note any additional decision memos or config knobs required (e.g., reserved IDs, naming conventions).

## 3. Initial Test Coverage (Pre-Coding)
- **Unit — Entry Store Gateway:** Add tests to `tests/unit/test_entrystore_gateway.py` that create/read/update `EntryType` rows (using in-memory SQLite) and verify default values (`active=True`, auto timestamps) plus unique constraints.
- **Unit — Semantic Worker Integration:** Extend `tests/unit/test_semantic_worker.py` with a scenario where semantic outputs include both `type_id` and `type_label`, ensuring the gateway persists labels even if IDs are missing, aligning with the advisory requirement.
- **API Contract Tests:** Plan new contract tests (likely under `tests/api/test_taxonomy_endpoints.py`) that validate request/response schemas once EF-07 controllers exist; for T01 we define the schema expected by these tests.
- **ETS-DB Scenario:** Define an ETS case (`ETS-DB-TAX-01`) that seeds a small set of EntryType rows, classifies Entries via `type_id`, then deactivates a Type to confirm entries stay readable. This scenario will later back the governance evidence for M03-T10.

## 4. Open Questions / Assumptions
- Assume Type IDs are lowercase slugs (e.g., `architecture_note`); confirm with M03-T12 naming decision later.
- No hierarchical relationships in v1.1; if future requirements add parent-child, this plan will need an addendum.

## 5. Next Steps
- Obtain approval (or amendments) for the subtasks above.
- Once accepted, update EF06 spec + supporting docs per ST01/ST02 before implementing migrations.
- Implement the planned tests prior to modifying production code, in keeping with ETS guidance.
