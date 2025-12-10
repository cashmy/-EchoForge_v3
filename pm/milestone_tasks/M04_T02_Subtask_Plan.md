# M04-T02 — Search & Filter Behavior Plan

## 1. Objective & Scope
- Define concrete `/api/entries` semantics for free-text search and filter combinations per M04 charter.
- Capture defaults (sort order, pagination, AND/OR rules) so EF-07 API + UI (T05/T06) can implement consistently.
- Provide guardrails for EF-06 query patterns and ETS validation later in M04-T08.

## 2. Reference Inputs
- `M04_Dashboard_Search_Aggregation_Tasks_v1.0.md` — milestone goals for search/filter + aggregation.
- `EF07_Api_Contract_v1.2.md` — `/api/entries` parameters, taxonomy pairing rules, error model.
- `EF07_EchoForgeApiAndUi_Spec_v1.1.md` — Entry List UX (filters, DataGrid expectations).
- `EF06_EntryStore_Spec_v1.1.md` + `EF06_EntryStore_Addendum_v1.2.md` — canonical fields (`ingest_state`, taxonomy IDs, timestamps, archived flag, pipeline/cognitive statuses) and index guidance.

## 3. Search Semantics
- **Free-text (`q`) scope:** Match against `display_title`, `summary`, `verbatim_preview`, `semantic_tags`, and optionally `normalized_text` when available. Stopgap implementation uses `ILIKE %term%` OR chain; later upgrade to PostgreSQL `tsvector` once T03 indexes finalize.
- **Case-insensitive, accent-insensitive** comparisons; rely on database collation or `lower()` wrappers until FTS lands.
- **Multiple terms** split on whitespace; all terms must appear somewhere (implicit AND) to keep noise low. Future enhancement may allow explicit OR/phrase syntax; document as out-of-scope for M04.
- **Highlighting** not returned by API in v1.0—UI can emphasize matched fields locally if needed.

## 4. Filter Model
- **AND combination** by default across distinct filter categories (`type_id`, `domain_id`, `pipeline_status`, etc.).
- Each filter accepts **comma-separated lists** to express OR within a category (e.g., `pipeline_status=processing_semantic,processed`). Server normalizes by splitting on comma and deduping.
- Supported filters v1.0:
  - `type_id`, `domain_id` (canonical IDs). When IDs absent, UI should fall back to labels but API continues filtering only on IDs.
  - `type_label`, `domain_label` (free-form) optional addition for manual reconciliation flows. Behavior: case-insensitive substring match; only enabled when `allow_label_filters` config flag true.
  - `pipeline_status` (alias for `ingest_state`) — accepts canonical states enumerated in EF06 addendum.
  - `cognitive_status` — enumerated set (`unreviewed`, `review_needed`, `processed`, `complete`, `needs_more`).
  - `source_channel` and `source_type` — allow multiple channels; default includes all.
  - `created_from` / `created_to` (ISO 8601). Inclusive bounds; validated so `from <= to`.
  - `updated_from` / `updated_to` for auditing recency filters needed by dashboard/needs-attention views.
  - `is_archived` boolean (default `false`). When omitted, archived entries excluded everywhere.

## 5. Sorting & Pagination Defaults
- Default sort: `updated_at DESC`, tie-breaker `id DESC` for deterministic pagination.
- Accept `sort_by` ∈ {`created_at`, `updated_at`, `display_title`, `pipeline_status`, `cognitive_status`}. Reject unsupported fields with `EF07-INVALID-REQUEST`.
- `sort_dir`: `asc` | `desc`, default `desc`.
- Pagination mirrors contract: `page` (1-indexed) default 1, `page_size` default 20, max 100. Requests exceeding max return `422` with bounds info.
- Response structure unchanged (items array + pagination metadata + `total_items`).

## 6. Query Planning & EF-06 Requirements
- Ensure indexes exist on `entries(type_id)`, `entries(domain_id)`, `entries(pipeline_status)`, `entries(cognitive_status)`, `entries(source_channel)`, `entries(created_at)`, `entries(updated_at)`, plus composite `(domain_id, type_id)` per EF06 addendum.
- Time range filters should leverage `created_at`/`updated_at` indexes with `BETWEEN` queries; avoid casting that would prevent index use.
- Comma-separated filter handling should translate to `IN (...)` for deterministic query plans.
- Free-text fallback uses sequential scan; T03 will introduce GIN/tsvector. Document expectation so ETS can tolerate slower dev data while verifying correctness.
- Enforce `LIMIT/OFFSET` derived from pagination; do not rely on `page` multiplication to avoid integer overflow. Use safe math.

## 7. API Validation & Error Handling
- Every filter parameter validated before hitting DB:
  - Enum fields checked against canonical lists; invalid value triggers `EF07-INVALID-REQUEST` with `details.invalid_fields` array.
  - Date filters parsed using strict ISO 8601; invalid formats produce `details.reason = "invalid_datetime"`.
  - When both `created_from` and `created_to` provided and `from > to`, return `EF07-INVALID-REQUEST` with `details.range = "created"`.
  - `q` limited to 256 chars to prevent unbounded wildcard scans; longer inputs trimmed with warning in logs.
- Unknown query parameters ignored? **Decision:** reject unknown params to keep contract strict; surfaces typos early.

## 8. Response Enrichment
- Each `items[]` object returns both canonical IDs and labels for taxonomy fields, plus `pipeline_status`, `cognitive_status`, `source_channel`, timestamps, and `summary_preview` snippet.
- When text search used, response includes `search_applied: true` flag at top-level so UI can show “Searching…” state.
- Include echo of applied filters in response metadata block `{ "filters": { ... } }` to help ETS confirm correct normalization (optional but recommended).

## 9. ETS Hooks (M04-T08 Alignment)
- `ETS-SEARCH-01`: Multi-filter AND combination returns expected subset (seed dataset with varied statuses).
- `ETS-SEARCH-02`: Comma-separated `pipeline_status` acts as OR within category while still AND-ing with `cognitive_status`.
- `ETS-SEARCH-03`: `q` filter combined with taxonomy IDs returns consistent results regardless of result ordering/pagination.
- `ETS-SEARCH-04`: `created_from`/`created_to` inclusive bounds enforced (edge-case entries exactly on boundary included once).
- `ETS-SEARCH-05`: `is_archived` default exclusion validated; explicit `true` includes archived rows.
- `ETS-SEARCH-06`: Invalid enum/date inputs return `EF07-INVALID-REQUEST` with informative details.

## 10. Open Questions / Follow-Ups
1. Should `/api/entries` expose `include_deleted_taxonomy=true` to filter by inactive IDs? Current assumption: IDs remain filterable regardless of `active` flag; UI indicates inactivity separately.
2. Is label-based filtering (without IDs) required for M04? Proposed to gate behind config to avoid expensive `ILIKE` scans unless governance demands it.
3. Need guidance on full-text search rollout timeline (tsvector). T03 dependency: once indexes ready, update this plan with exact operator support (phrase search, weighting).
4. Consider cursor-based pagination for future SaaS shape; out-of-scope for M04 but note as MG07 topic.

## 11. Hand-off Notes
- This plan informs T03 index prioritization and T05 API implementation. Any deviations should note reasons in milestone status log.
- UI team (T06) can wire filter controls directly to the parameters defined here, ensuring consistent behavior between SPA and API automation.
