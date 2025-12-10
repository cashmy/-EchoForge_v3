# M04-T04 — `/api/dashboard/summary` Implementation Plan

## 1. Objective & Scope
- Implement backend aggregation logic for `GET /api/dashboard/summary` aligning with KPIs defined in T01 and supported by indexes from T03.
- Ensure the endpoint serves pipeline/cognitive counts, taxonomy leaderboards, momentum slices, and attention queues with predictable latency on local + SaaS runtimes.
- Establish response schema, query strategy, caching, and ETS hooks so T04/T06 hand-off is deterministic.

## 2. Reference Inputs
- `M04_Dashboard_Search_Aggregation_Tasks_v1.0.md` — milestone charter + dependencies.
- `M04_T01_Subtask_Plan.md` — widget definitions, default filters, attention rules.
- `M04_T03_Subtask_Plan.md` — index availability & query shapes.
- `EF07_Api_Contract_v1.2.md` — `/api/dashboard/summary` contract skeleton + taxonomy ID/label expectations.
- `EF06_EntryStore_Spec_v1.1.md` + Addendum v1.2 — canonical fields, ingest/cognitive states, archival semantics.

## 3. Response Schema (v1.0)
```json
{
  "pipeline": {
    "total": 0,
    "by_ingest_state": {"captured": 0, ...},
    "failure_window": {
      "since": "2025-12-03T00:00:00Z",
      "counts": {"transcription_failed": 0, ...}
    }
  },
  "cognitive": {
    "by_status": {"unreviewed": 0, ...},
    "needs_review": {
      "items": [
        {"id": "entry_123", "display_title": "...", "updated_at": "...", "pipeline_status": "semantic_complete"}
      ]
    }
  },
  "momentum": {
    "recent_intake": [
      {"date": "2025-12-04", "count": 4}
    ],
    "source_mix": [
      {"source_channel": "watch_folder_audio", "count": 12}
    ]
  },
  "taxonomy": {
    "top_types": [
      {"type_id": "BookIdea", "type_label": "Book Idea", "count": 25}
    ],
    "top_domains": [
      {"domain_id": "Architecture", "domain_label": "Architecture", "count": 30}
    ]
  },
  "recent": {
    "processed": [
      {"id": "entry_789", "display_title": "..", "updated_at": "..."}
    ]
  },
  "meta": {
    "generated_at": "2025-12-10T12:00:00Z",
    "time_window_days": 7,
    "include_archived": false
  }
}
```
- All numeric counts default to 0, arrays default to `[]`.
- `meta.generated_at` uses UTC timestamp.
- `time_window_days` echo ensures UI/ETS verify applied range.

## 4. Query & Aggregation Strategy
1. **Pipeline counts**
   - SQL: `SELECT ingest_state, COUNT(*) FROM entries WHERE is_archived = FALSE GROUP BY ingest_state;`
   - Summation yields `pipeline.total`.
   - Use `idx_entries_ingest_state`.
2. **Failure spotlight**
   - Window filter: `updated_at >= NOW() - INTERVAL :failure_days` (default 7) AND `pipeline_status LIKE '%_failed'`.
   - Group by `pipeline_status`.
3. **Cognitive distribution**
   - Similar to pipeline: group `cognitive_status` with `is_archived = FALSE`.
4. **Needs Review list**
   - Reuse `/api/entries` query builder with filters: `cognitive_status IN ('unreviewed','review_needed')` AND `ingest_state IN ('processing_semantic','processed')` AND `is_archived=FALSE`.
   - Limit 10, sort `updated_at DESC`.
5. **Recent intake sparkline**
   - Precompute array of last `recent_days` (default 14) via generate_series; join to counts of entries grouped by `date(created_at)` using timezone-safe truncation (`date_trunc('day', created_at AT TIME ZONE 'UTC')`).
6. **Source channel mix**
   - Filter `created_at >= NOW() - INTERVAL :source_mix_days` (default 30) and `is_archived=FALSE`.
   - Group by `source_channel`, order desc, optionally cap to top 8 with `OTHER` bucket for remaining.
7. **Taxonomy leaderboards**
   - Use counts grouped by `type_id`/`domain_id`; LEFT JOIN to taxonomy tables for labels.
   - Sort by `count DESC`, limit 5 each. Fall back to `type_label`/`domain_label` when join NULL.
8. **Recently processed list**
   - Filter `ingest_state='processed' AND is_archived = FALSE`.
   - Sort `updated_at DESC`, limit 5.

## 5. Implementation Notes
- Use a dedicated service module `dashboard_summary_service.py` orchestrating queries via EF-06 repository functions.
- Prefer **single round-trip** by issuing aggregated SQL per section instead of fetching all entries. Some queries can be batched using CTEs when beneficial.
- All time window defaults driven by config (`dashboard.summary.failure_days`, `recent_days`, `source_mix_days`). Validate inputs if endpoint allows overrides (M04 scope: read-only defaults, optional `time_window_days` query param for momentum + failure sections).
- Ensure `include_archived` query param is future-ready; for now default false and reject true with `EF07-UNSUPPORTED` to avoid undefined semantics.
- Response ordering: deterministic sorts for arrays (counts desc, ties by label ascending).

## 6. Performance & Caching
- Target p95 latency < 150ms on dataset of 50k entries (desktop hardware) and < 80ms on SaaS shape.
- Implement **per-request caching** only when endpoint invoked multiple times during same HTTP request (not expected). Instead, add optional in-memory cache layer (TTL 30s) behind config for desktop runtime to reduce repeated calculations when dashboard auto-refreshes. Document but default disabled to avoid staleness.
- Use database transactions with `READ COMMITTED` isolation; this is acceptable because data is read-only.

## 7. Error Handling & Observability
- Input validation: `time_window_days` must be int between 1 and 30; invalid returns `EF07-INVALID-REQUEST`.
- Log query execution times per section at DEBUG; emit structured INFO log summarizing counts + latency for governance.
- Metrics: expose `dashboard_summary_duration_ms` histogram, `dashboard_summary_errors_total`, and per-section timers if instrumentation available.

## 8. ETS Hooks (aligning with T01/T08)
- `ETS-DASH-01`: Pipeline counts sum equals expected seeded total minus archived.
- `ETS-DASH-02`: Needs-review list respects ingest/cognitive filters and ordering.
- `ETS-DASH-03`: Taxonomy leaderboards include fallback labels when IDs missing/deactivated.
- `ETS-DASH-04`: Time-windowed sections honor `time_window_days` param and UTC boundaries.
- `ETS-DASH-05`: Failure spotlight only includes `*_failed` statuses within window.
- Record SQL snapshots in ETS artifact for reproducibility.

## 9. Open Questions / Follow-Ups
1. Should we precompute pipeline buckets (capture/processing/semantic) in addition to raw ingest states? Could add derived fields later once UX confirms need.
2. Do we need to internationalize date buckets (e.g., locale-specific week start)? For now aggregator emits ISO dates; UI handles localization.
3. Evaluate materialized views for SaaS scale if counts exceed latency budget after implementation.

## 10. Hand-off Notes
- This plan unblocks T04 implementation work plus T06 UI wiring because payload structure + defaults are fixed.
- Update milestone status & future status logs when implementation begins; capture deviations (e.g., caching changes) in `pm/status_logs/`.
