# M04-T07 — Saved Filters / Views Design (Provisional)

## 1. Objective & Scope
- Capture initial thoughts on “saved views” (filter presets, pinned filters) even though the feature may be optional or deferred.
- Provide inputs for governance decisions in T10 and future milestones.

## 2. Current Context (2025-12-10)
- Core search/filter semantics defined (T02) but UI not yet implemented.
- Saved views likely depend on both `/api/entries` implementation (T05) and UI wiring (T06).
- No persistence layer exists for saved views; decision needed on storage (local config vs EF-06 table vs config service).

## 3. Potential Tasks / Questions
1. **Use Cases & Personas**
   - Identify who benefits most: reviewers, domain experts, ingestion operators.
   - Determine what should be saved (query string, filters, sort order, pagination?)
2. **Storage Strategy**
   - Options: local JSON, config service, dedicated EF-06 table; capture pros/cons.
   - Consider user-specific vs global views, sharing, permissions.
3. **API & UI Impacts**
   - Define endpoints (if any) to manage saved filters.
   - UI requirements for listing, selecting, and managing views.
4. **Deferral Criteria**
   - Document what must be true before implementation (e.g., stable filter model, user auth context).
   - Outline ETS considerations if/when implemented.

## 4. References
- `M04_T02_Subtask_Plan.md` — baseline filter behavior.
- `M04_T06_Subtask_Plan.md` — UI wiring notes.
- `pm/decisions/` (future) — capture decisions made once scope is clarified.
