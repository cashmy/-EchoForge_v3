# M04-T01 — Dashboard Use Cases & KPIs Plan

## 1. Objective & Scope
- Translate M04 charter into concrete dashboard intent for EF-07 desktop/web UI.
- Enumerate the questions/insights the dashboard must answer and map them to EF-06 data + EF-07 API behavior.
- Provide guardrails for later tasks (T03 indexing, T04 aggregation, T06 UI wiring) plus ETS focus areas.

## 2. Reference Inputs
- `M04_Dashboard_Search_Aggregation_Tasks_v1.0.md` — milestone goals, task lattice, exit criteria.
- `EF07_EchoForgeApiAndUi_Spec_v1.1.md` — dashboard UX expectations (summary cards, needs-attention, customization hooks).
- `EF07_Api_Contract_v1.2.md` — `/api/dashboard/summary` + `/api/entries` contract; taxonomy pair semantics.
- `EF06_EntryStore_Spec_v1.1.md` + `EF06_EntryStore_Addendum_v1.2.md` — canonical fields (`ingest_state`, `pipeline_status`, `cognitive_status`, taxonomy overlays, timestamps, archival flags, semantic outputs) and recommended indexes.

## 3. Primary Dashboard Questions (v1.0)
1. **Pipeline health** — How many entries sit in each ingest/pipeline stage? Where are items stuck or failing?
2. **Cognitive workload** — Which entries still need review vs are complete? How fast is review happening?
3. **Recent capture momentum** — What just arrived in the last 24h/7d? Are there spikes by source channel?
4. **Taxonomy distribution** — Which domains/types dominate the workspace this week? Are any underserved?
5. **Attention queue** — Which entries require human action now (e.g., `cognitive_status` in `unreviewed`/`review_needed`)?

## 4. KPI & Widget Proposal
| Section | Widget | Definition | Data Source | Default Filters |
| --- | --- | --- | --- | --- |
| Pipeline Health | `Pipeline Distribution` stacked bar | Count entries grouped by `ingest_state` (or coarse buckets: capture, processing, semantic, processed, failed). | `entries` table (EF-06). | `is_archived = FALSE`; timeframe = all-time.
| Pipeline Health | `Failure Spotlight` vector | Entries in `failed` ingest_state grouped by `pipeline_status` (`*_failed`). | `entries`. | Last 7 days.
| Cognitive Workload | `Cognitive Status Ring` | Count per `cognitive_status` (unreviewed, review_needed, processed, complete). | `entries`. | `is_archived = FALSE`.
| Cognitive Workload | `Needs Review list` | Top N entries ordered by `updated_at desc` where `cognitive_status` ∈ {`unreviewed`, `review_needed`} and `pipeline_status` indicates semantic complete or ready. | `/api/entries` search (server paginated). | Limit 10.
| Capture Momentum | `Recent Intake` sparkline | Daily counts for last 14 days based on `created_at`. | `entries`. | Use timezone-safe date truncation.
| Capture Momentum | `Source Channel mix` | Pie list of counts grouped by `source_channel`. | `entries`. | Last 30 days.
| Taxonomy Mix | `Top Domains` leaderboard | Top 5 domains by `domain_id`/`domain_label` count. | `entries` joined with `entry_domains`. | All active entries.
| Taxonomy Mix | `Top Types` leaderboard | Top 5 types by `type_id`/`type_label` count. | `entries` joined with `entry_types`. | All active entries.
| Attention Queue | `Recently Processed` | Latest semantic-complete entries (descending `updated_at`). | `/api/entries`. | Limit 5.

Implementation guidance:
- Widgets should default to `is_archived = FALSE`; allow toggles later.
- Taxonomy widgets fall back to stored labels when `type_id`/`domain_id` null or inactive, per EF07 contract.

## 5. Data & Query Requirements
- **Counts** use pure EF-06 aggregations; avoid loading entire rows.
- **Time slicing**: adopt `created_at >= NOW() - INTERVAL 'X days'` filters for recency-based widgets. Keep time window constants in config for ETS determinism.
- **Needs Review rule**: `cognitive_status IN ('unreviewed','review_needed') AND ingest_state IN ('processed','processing_semantic')` so we only surface items past normalization. Documented in ETS.
- **Archival guard**: all dashboard queries exclude `is_archived = TRUE` unless API caller passes `include_archived=true` (future flag). This keeps metrics actionable.
- **Taxonomy joins**: use LEFT JOIN to `entry_types` / `entry_domains` to capture inactive IDs but still display counts; include `label` fallback when join misses.
- **Recency lists** rely on `/api/entries` existing pagination to avoid bespoke SQL; back-end still needs sort indexes (`created_at desc`, `updated_at desc`).

## 6. API Contract Considerations
- `/api/dashboard/summary` response should expose structured sections aligning with table above (e.g., `pipeline`, `cognitive`, `taxonomy`, `recent`, `attention`).
- Provide optional `time_window_days` query param (default 7) for momentum widgets; backend clamps to safe range (1–30) to prevent heavy scans.
- Ensure response includes both ID + label for taxonomy groupings, matching EF07 contract pattern.
- Clarify zero-state behavior: return empty arrays and zero counts, not HTTP 204, so UI can render placeholders.

## 7. ETS Coverage Hooks (for T08)
- `ETS-DASH-01`: pipeline distribution sums match total entries minus archived for seeded dataset.
- `ETS-DASH-02`: needs-review widget only includes entries with target statuses and respects `is_archived` flag.
- `ETS-DASH-03`: taxonomy leaderboards fall back to labels when IDs removed/deactivated.
- `ETS-DASH-04`: time-windowed counts respond to varying `time_window_days` inputs without drifting due to timezone boundaries (UTC tests).

## 8. Open Questions / Follow-Ups
1. Should `/api/dashboard/summary` support user-specific saved widget layouts? **Proposal:** defer to optional M04-T07; keep API global for now.
2. Do we expose trend deltas (+/- vs prior week) in v1.0? **Proposal:** not yet; record as MG06 candidate once baseline metrics land.
3. What is the maximum dataset size assumed for desktop deployments? Need expectation to size indexes (feed into T03).
4. Confirm whether `source_channel` should be user-configurable filter on dashboard or only visible inside widget tooltip.

## 9. Hand-off Notes
- This doc unblocks T03/T04 by specifying fields/groupings for indexes and aggregation queries.
- UI (T06) can map each widget to a component + API field now, ensuring no surprises when wiring React SPA.
