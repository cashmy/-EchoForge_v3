# M04-T06 — Dashboard & Entry List UI Wiring Plan

## 1. Objective & Scope
- Wire the Electron/SPA frontend to use `/api/dashboard/summary` and `/api/entries` once backend endpoints are finalized.
- Provide implementation notes so UI work can begin immediately when frontend resources become available.

## 2. Current Context (2025-12-10)
- `/api/dashboard/summary` is implemented with FastAPI + tests. Payload structure documented in M04-T04 plan.
- `/api/entries` backend work is pending (T05) but the search/filter spec is fixed (T02 plan).
- No production-ready UI yet; only wireframes exist. This document captures assumptions for future UI dev.

## 3. Tasks / Subtasks (Initial Draft)
1. **Dashboard Widgets**
   - Build components for pipeline distribution, cognitive status ring, needs-review list, taxonomy leaderboards, momentum trends.
   - Map each component to the response schema fields (see T04 plan / Postman collection).
   - Handle zero-state rendering and auto-refresh cadence (configurable interval).
2. **Entry List & Filters**
   - Implement search input, taxonomy dropdowns, status chips, date pickers tied to `/api/entries` query params.
   - Integrate pagination controls (page/page_size) with default `updated_at desc` sorting.
   - Provide applied-filter summary to mirror API `filters` payload (once implemented).
3. **State Management & API Layer**
   - Centralize API calls (e.g., React Query / Redux Query) with error handling aligned to EF07 error codes.
   - Provide optimistic loading indicators and fallback content.
4. **Testing & ETS Alignment**
   - Define basic UI smoke tests (component-level) verifying data binding.
   - Plan for ETS visual checks once MG06 governance kicks in.

## 4. Open Questions / Follow-ups
- Confirm design system / component library choice for Electron UI.
- Define auto-refresh cadence and whether it is user-configurable.
- Determine how saved filters (T07) will influence default state or layout.

## 5. References
- `M04_T01_Subtask_Plan.md` — dashboard KPI definitions.
- `M04_T02_Subtask_Plan.md` — search/filter model.
- `M04_T04_Subtask_Plan.md` — `/api/dashboard/summary` response schema.
- `tools/postman/echo_forge_dashboard.postman_collection.json` — handy request samples for UI developers.
