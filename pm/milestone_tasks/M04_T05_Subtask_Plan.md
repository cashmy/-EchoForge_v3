# M04-T05 — `/api/entries` Search & Filter Implementation Plan

## 1. Objective & Scope
- Implement the backend portion of `/api/entries` per the behavior defined in `M04_T02_Subtask_Plan.md`.
- Ensure EF-06 querying aligns with the indexes documented in `M04_T03_Subtask_Plan.md`.
- Provide enough detail for ETS coverage (M04-T08) and later UI wiring (M04-T06).

## 2. Current Context (2025-12-10)
- Search/filter requirements finalized (see T02 plan) but not yet implemented in FastAPI.
- `/api/dashboard/summary` is live and will drive demand for consistent filter semantics between widgets and entry list views.
- EF-06 indexes (pipeline status, taxonomy fields, timestamps) have been applied via latest Alembic migrations (`alembic upgrade head`).

## 3. Tasks / Subtasks (Initial Draft)
1. **Query Builder & Validation**
   - Create reusable filter parser handling `q`, taxonomy IDs, statuses, date ranges, pagination, and sort validation.
   - Enforce canonical enums with descriptive `EF07-INVALID-REQUEST` errors.
2. **Gateway + Repository Wiring**
   - Extend EF-06 gateway/repository (or add dedicated query service) to issue SQL with AND-combined filters and pagination.
   - Support future FTS upgrade but default to `ILIKE` fallback.
3. **FastAPI Endpoint Implementation**
   - Flesh out `GET /api/entries` handler in `backend/app/api/routers/entries.py` returning paginated payloads with `filters` echo block.
4. **ETS / Unit Tests**
   - Add unit coverage for filter combos and archived behavior.
   - Prepare scenarios to feed into ETS-T08.

## 4. Open Questions / Follow-ups
- Do we need optimistic cursor-based pagination once SaaS runtime is targeted? (Track under MG07.)
- Should label-only filtering (without IDs) be enabled in v1.0 or gated via config flag?
- Confirm default page size (20) vs. ETS expectations.

## 5. References
- `M04_T02_Subtask_Plan.md` — search & filter spec.
- `EF07_Api_Contract_v1.2.md` — `/api/entries` contract and error codes.
- `EF06_EntryStore_Spec_v1.1.md` + Addendum — canonical fields and ingest/cognitive states.
- `backend/app/api/routers/entries.py` — existing taxonomy patch scaffolding (needs list implementation).
