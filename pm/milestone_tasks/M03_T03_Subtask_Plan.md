# M03-T03 — Subtask Plan & Initial Test Matrix

_Date:_ 2025-12-09  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `M03_Taxonomy_Classification_Tasks_v1.1.md` scopes T03 as the EF-06 work needed to add `type_id` and `domain_id` references while keeping the legacy label fields readable. The task depends on T01/T02 schemas.
- `EF06_EntryStore_Addendum_v1.2.md §7.2` already documents the new nullable columns, advisory nature, and atomically-updated `{id, label}` pairs; §7.2.1 and §7.4 spell out soft-delete semantics and indexing expectations.
- `backend/app/domain/ef06_entrystore/pipeline_states.py` and `tests/unit/test_entrystore_gateway.py` currently assume only label fields exist. Updating them will require new gateway DTOs plus tests once we move beyond the design stage.
- ETS governance (`protocols/ETS/EchoForge_Testing_Philosophy_v0.1.md`) mandates defining the test matrix before implementing schema or gateway changes; this plan captures those expectations.

## 2. Proposed Subtasks
1. ✅ **TT01 — Document Reference Columns in EF06 Addendum:** Ensure §7.2 captures field definitions, nullability, and advisory behavior for `type_id` / `domain_id`, plus the rule that labels must always be written alongside IDs.
2. ✅ **TT02 — Specify Referential Semantics & UI Fallbacks:** Leverage §7.2.1 to detail how deactivated or deleted taxonomy entries affect `type_id`/`domain_id`, including client fallback requirements and orphan-handling guidance.
3. ✅ **TT03 — Outline Migration & Indexing Requirements:** Use §7.4–§7.5 to define the required indexes (`entries(type_id)`, `entries(domain_id)`) and phased deployment plan that keeps EF-05/EF-07 backward compatible.
4. ✅ **TT04 — EntryStore Gateway Blueprint:** Describe required changes to the gateway/domain models so application code can read/write the new columns while keeping label fallbacks. Reference the files (`backend/app/gateway/entrystore.py`, semantic worker) that will need updates in future milestones (see §4).
5. ✅ **TT05 — ETS/Test Coverage Definition:** Extend this plan with concrete unit/API/ETS tests that must be authored once code changes begin (e.g., verifying Entries persist both IDs and labels, ensuring queries can filter on the new columns). Details captured in §5.

## 3. Initial Test Coverage (Pre-Coding)
- **Unit — EntryStore Gateway:** Add tests ensuring CRUD operations on Entries can set/get `type_id`/`domain_id` independently, verifying that labels remain untouched when IDs are null. These belong in `tests/unit/test_entrystore_gateway.py`.
- **Unit — Semantic Worker:** Plan a test in `tests/unit/test_semantic_worker.py` that mocks taxonomy lookup results and asserts both IDs and labels are persisted atomically, including the label-only fallback path.
- **API Contract:** Future EF-07 entry update endpoints must validate `{type_id, type_label}` and `{domain_id, domain_label}` pairs; contract tests should cover rejection of half-populated payloads.
- **Migration Tests:** Plan Alembic/SQL migration tests ensuring new columns default NULL, maintain existing data, and can be rolled back cleanly.
- **ETS Scenario:** Draft `ETS-DB-TAX-03` (new) that seeds taxonomy tables, writes Entries referencing them, then deletes/deactivates taxonomy rows to confirm Entries still display labels and queries remain stable.

## 4. EntryStore Gateway & Worker Blueprint (TT04)

- **Gateway Model updates:**
	- `backend/app/gateway/entrystore.py` — expand `EntryRecord`/`EntryRow` dataclasses (or dict mappers) to include `type_id`, `type_label`, `domain_id`, `domain_label`. Ensure serialization/deserialization keeps labels even when IDs are NULL.
	- `backend/app/db/entrystore_repository.py` (or equivalent query builder) — update column lists in `INSERT`/`UPDATE`/`SELECT` statements plus row factories so optional IDs round-trip. Where helper functions currently reference `entry.type_label`, add paired ID handling and default to NULL when unspecified.
	- `backend/app/domain/entries/models.py` — add optional fields (with typing) so upstream services (EF-05, EF-07) can pass IDs without modifying unrelated code.
- **Persistence semantics:**
	- `save_entry()` pathways must enforce the atomic rule: caller must provide both ID and label; gateway rejects ID-only writes (raise `ValueError`) to match EF06 §7.2.1.
	- Provide helper method `apply_taxonomy_reference(entry, taxonomy_ref)` that sets both fields in one call, simplifying EF-05 and EF-07 integrations.
- **Semantic worker touch points:**
	- `backend/app/jobs/semantic_worker.py` currently writes `type_label`/`domain_label`. Blueprint adds lookup helper (likely in `backend/app/services/taxonomy_mapper.py`) that takes semantic suggestions, matches them to canonical IDs, and returns `{id, label}` pairs.
	- Worker must log when it fails to resolve a canonical ID and leave the ID NULL while retaining the label (per EF06 addendum). Blueprint calls for a feature flag to gate ID writes until migrations finish.
- **Query & filtering surfaces:**
	- Future EF-07 search endpoints and dashboards require repository filters for `type_id`/`domain_id`. Add TODO comments pointing to `backend/app/gateway/queries/entry_filters.py` with placeholder predicate signatures so implementation tickets have a clear target.
- **Rollout sequencing:**
	- Step 1: ship migrations adding columns.
	- Step 2: update gateway to read (but not yet write) IDs, guarded by `ENABLE_TAXONOMY_IDS` config flag.
	- Step 3: enable writes in EF-05/EF-07 once all environments confirm schema availability.

## 5. Detailed ETS/Test Coverage Commitments (TT05)

- **Unit Tests:**
	- Extend `tests/unit/test_entrystore_gateway.py` with scenarios covering: insert/update with both ID+label, label-only fallback, rejection of ID-only payloads, and query filtering by ID.
	- Update `tests/unit/test_semantic_worker.py` to mock taxonomy matches vs misses, asserting capture-event logging when IDs change.
- **Migration/DB Tests:**
	- Write Alembic tests verifying new columns default to NULL, inherit existing data untouched, and maintain indexes `entries(type_id)` / `entries(domain_id)` after downgrade.
- **API Contract Tests:**
	- When EF-07 entry update endpoints land, add contract tests ensuring payload validation fails for `{type_id}` without `type_label` (and vice versa) and that responses echo both fields.
- **ETS Scenarios:**
	- `ETS-DB-TAX-03`: described earlier; ensures Entries survive taxonomy deactivation/deletion while filters rely on ID.
	- `ETS-API-TAX-01`: new scenario that walks through EF-07 update flow, confirming capture events log ID changes and that UI receives deactivation warnings.
- **Observability Hooks:**
	- Blueprint includes `capture_event` emission (`taxonomy.reference.updated`) whenever either ID changes; TT05 requires test coverage ensuring the event fires exactly once per update and includes `{entry_id, old_id, new_id, label}` payload.

## 6. Open Questions / Assumptions
- Entry updates remain advisory until EF-07 edit APIs exist; interim tooling may update IDs via SQL/admin interfaces. This plan assumes no automatic reconciliation besides governance-approved scripts.
- We assume no hard foreign keys on `type_id`/`domain_id` in v1.2; enforcing referential integrity would require additional migration safeguards and is deferred per milestone scope.
- Whether Entry history should log taxonomy changes as separate audit events is deferred to M03-T12 governance, but TT05 should note any capture-event scaffolding needed.

## 7. Next Steps
- Socialize this plan via the milestone file (status + checklist) and obtain approval.
- Flesh out TT04/TT05 details (gateway blueprint + ETS coverage) before implementing schema migrations or code changes.
- Once approved, align EF-06 migration tickets with the phase plan in §7.5 and ensure EntryStore gateway changes are sequenced with EF-07 API work.
