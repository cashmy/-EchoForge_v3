# M03-T05 — Subtask Plan & Initial Test Matrix

_Date:_ 2025-12-09  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `M03_Taxonomy_Classification_Tasks_v1.1.md` scopes T05 as the actual implementation of `/api/types` and `/api/domains` CRUD endpoints defined in T04.
- `EF07_Api_Contract_v1.2.md §8` now codifies detailed payload rules, pagination, delete gating, and observability requirements (UT01–UT05). This plan maps those contract changes to concrete code/files and test needs.
- The backend currently exposes only entry-related endpoints. There are no existing taxonomy controllers, so we will introduce new FastAPI/Flask blueprints (depending on runtime) and reuse the EntryStore gateway once taxonomy tables land.
- EF-06 migrations (T01–T03) ensure taxonomy tables/columns exist, but the gateway/services still need to be extended to read/write them; T05 will implement that plumbing alongside HTTP handlers.

## 2. Proposed Subtasks
1. ✅ **VT01 — Controller & Routing Skeletons:** Completed via `backend/app/api/routers/taxonomy.py`; routers now expose `/api/types` and `/api/domains` with shared schemas + DI plumbing (commit 2025-12-09).
2. ✅ **VT02 — Validation & Business Rules:** Enforced slug/id rules, case-insensitive name uniqueness, delete gating, and response semantics via `backend/app/domain/taxonomy/service.py` plus new controller delete behavior/tests (`tests/unit/test_taxonomy_service.py`).
3. ✅ **VT03 — Persistence Integration:** Replaced the in-memory store with repository adapters (`backend/app/domain/taxonomy/repository.py`) and wired API dependency to use the Postgres-backed version so CRUD now persists via EF-06 tables and surfaces `referenced_entries` counts.
4. ✅ **VT04 — Observability & Capture Events:** Wire INF-03 logging, capture-event emission (`taxonomy.*`, `taxonomy.reference.*`), and metrics counters.
5. ✅ **VT05 — Tests & ETS Hooks:** Add unit tests for controllers/services, API contract tests for success/error cases, and ensure ETS scenarios (ETS-API-TAX-01, ETS-DB-TAX-03) have implementation notes/owners.

## 3. Initial Test Coverage (Pre-Coding)
- **Unit:**
  - Controller tests verifying validation errors, `allow_taxonomy_delete` gate, `deletion_warning` behavior, and event emission stubs.
  - Repository tests for create/update/delete flows, ensuring dependency counts and label preservation.
- **API/Contract:** Expand `tests/api/test_taxonomy_types.py` / `..._domains.py` to cover 200/201/204, duplicate ID conflicts, invalid slug, reactivation, and delete gating.
- **Integration:** Smoke test (`tests/integration/test_taxonomy_entry_roundtrip.py`) that creates a taxonomy row, assigns it to an Entry, deactivates it, and confirms GET endpoints surface `deletion_warning`.
- **ETS:** Assign owners for `ETS-API-TAX-01` and `ETS-DB-TAX-03` verifying audit logs and DB resilience. Tests should ingest fixture data via the new endpoints rather than manual SQL to keep coverage realistic.

## 4. Open Questions / Assumptions
- Implementation language/framework: assuming FastAPI (py) per existing EF-07 code; confirm before scaffolding.
- Need to confirm whether governance requires dual-operator confirmation for hard delete; if yes, this plan will add a review hook before enabling `allow_taxonomy_delete` in prod.
- Capture-event topics (`taxonomy.type.*`) will be implemented via existing INF-03 publisher; ensure dependencies are available in the EF-07 service container.

## 5. Next Steps
- Get sign-off on the subtasks/test matrix.
- Update milestone checklist, then begin VT01 by scaffolding shared router/schemas while referencing EF07 contract.
- Sequence VT02–VT05 with migrations ready, ensuring we add feature flags/configs where necessary for safe rollout.
