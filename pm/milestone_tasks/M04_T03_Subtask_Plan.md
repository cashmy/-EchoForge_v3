# M04-T03 — EF-06 Indexing Plan

## 1. Objective & Scope
- Ensure EF-06 (EntryStore) and taxonomy tables have indexes tuned for dashboard counts (`/api/dashboard/summary`) and `/api/entries` search filters defined in T01/T02.
- Cover both baseline Postgres (desktop/local) and future SaaS expectations, documenting tradeoffs so T04/T05 implementation can rely on deterministic query performance.

## 2. Reference Inputs
- `M04_Dashboard_Search_Aggregation_Tasks_v1.0.md` — scope + exit criteria.
- `M04_T01_Subtask_Plan.md` — dashboard widget/query requirements.
- `M04_T02_Subtask_Plan.md` — search/filter semantics and parameter list.
- `EF06_EntryStore_Spec_v1.1.md` + `EF06_EntryStore_Addendum_v1.2.md` — canonical schema, ingest state definitions, recommended baseline indexes.
- `EF07_Api_Contract_v1.2.md` — `/api/entries` and `/api/dashboard/summary` contracts.

## 3. Target Query Shapes
1. **Pipeline distribution**: `SELECT ingest_state, COUNT(*) FROM entries WHERE is_archived=FALSE GROUP BY ingest_state;`
2. **Cognitive workload**: same pattern over `cognitive_status`.
3. **Taxonomy leaderboards**: counts by `type_id`/`domain_id` with LEFT JOIN to taxonomy tables for labels; filters may include inactive IDs.
4. **Recent activity**: `created_at`/`updated_at` range scans with optional `source_channel` filter.
5. **Search/filter listings**: multi-criteria `WHERE` clauses combining taxonomy, statuses, source metadata, `is_archived`, and time bounds, sorted by `updated_at DESC`.
6. **Free-text search**: `ILIKE` fallback now, migrating to Postgres `tsvector` GIN index for `display_title`, `summary`, `verbatim_preview`, `semantic_tags`.

## 4. Index Recommendations
| Table | Index Name | Columns / Type | Purpose |
| --- | --- | --- | --- |
| `entries` | `idx_entries_ingest_state` | `(ingest_state)` btree | Pipeline distribution counters, filters. |
| `entries` | `idx_entries_pipeline_status` | `(pipeline_status)` btree | Backward compatibility + filters that still use legacy name. |
| `entries` | `idx_entries_cognitive_status` | `(cognitive_status)` btree | Cognitive workload widgets, filters. |
| `entries` | `idx_entries_created_at` | `(created_at DESC)` btree | Recent intake timelines, `created_from/to` filters. |
| `entries` | `idx_entries_updated_at` | `(updated_at DESC)` btree | Default sort for `/api/entries`, needs-attention lists. |
| `entries` | `idx_entries_type_id` | `(type_id)` btree | Taxonomy filters, leaderboard joins. |
| `entries` | `idx_entries_domain_id` | `(domain_id)` btree | Same for domains. |
| `entries` | `idx_entries_domain_type` | `(domain_id, type_id)` btree | Combined filters + cross-tab dashboards. |
| `entries` | `idx_entries_source_channel` | `(source_channel)` btree | Source mix widget + filter. |
| `entries` | `idx_entries_is_archived` | `(is_archived)` partial | Partial index `(is_archived = TRUE)` to keep archival scans cheap without bloating active queries. |
| `entries` | `idx_entries_text_search` | `GIN (to_tsvector('english', coalesce(display_title,'') || ' ' || coalesce(summary,'') || ' ' || coalesce(verbatim_preview,'')))` | Enables scalable `q` search when enabled. Deployed behind feature flag until migration tested. |
| `entry_types` | `idx_entry_types_active_sort` | `(active, sort_order)` btree | Keeps dropdown queries fast. |
| `entry_domains` | `idx_entry_domains_active_sort` | `(active, sort_order)` btree | Same for domains. |
| `entry_types` | `idx_entry_types_updated_at` | `(updated_at)` | Supports `updated_after` pagination in taxonomy APIs. |
| `entry_domains` | `idx_entry_domains_updated_at` | `(updated_at)` | Same. |

Additional guidance:
- Reuse existing unique/PK indexes; avoid duplicates by checking migration history before applying new names.
- `idx_entries_text_search` optional in desktop builds; still document DDL so SaaS shape can enable it immediately.

## 5. Deployment Strategy
1. **Phase A — Schema Audit**: Inspect current indexes via `pg_indexes`; drop/rename duplicates before adding new ones to keep migration idempotent.
2. **Phase B — Incremental Migration**:
   - Create missing btree indexes online (`CREATE INDEX CONCURRENTLY`) to avoid blocking writes.
   - For `idx_entries_domain_type`, ensure column order matches most common filter (domain first, then type per dashboard use cases).
   - Add partial archival index only if archive volume > 5% of table; otherwise rely on `is_archived` filter within compound indexes.
3. **Phase C — Text Search Enablement**:
   - Introduce computed `tsvector` column or functional index; ensure `gin_trgm_ops` alternative available if `pg_trgm` extension allowed.
   - Gate behind config `enable_full_text_search`. When false, `/api/entries` uses existing `ILIKE` path; queries still benefit from other indexes.
4. **Phase D — Verification**:
   - Run `EXPLAIN ANALYZE` for representative queries (Sections 3.1–3.5) on seeded dataset (~50k entries) to confirm index usage under both local (single-node) and SaaS (managed Postgres) assumptions.

## 6. Tradeoffs & Environment Notes
- **Desktop / Local Postgres**: Prioritize minimal storage overhead; accept slower text search until user enables full-text flag. Ensure migrations run quickly (limit concurrent index builds to avoid laptop resource spikes).
- **SaaS / Hosted**: Enable full index set, including text search; consider additional partial indexes for `pipeline_status` subsets if traffic shows skew. Document maintenance windows for `CREATE INDEX CONCURRENTLY`.
- **Write Overhead**: Additional indexes increase insert/update cost; capture this in logging and only add indexes justified by query volume (focus on read-heavy fields enumerated above).

## 7. ETS Hooks
- `ETS-IDX-01`: Verify `/api/dashboard/summary` queries hit the intended indexes (use EXPLAIN snapshot in test artifacts).
- `ETS-IDX-02`: `/api/entries` multi-filter query stays under target latency using seeded dataset; includes scenario with taxonomy filters + date range.
- `ETS-IDX-03`: `q` search falls back gracefully when text index disabled; when enabled, `EXPLAIN` shows GIN usage.
- `ETS-IDX-04`: Archival partial index prevents archived-only queries from scanning entire table. Include test case toggling `is_archived=true`.

## 8. Open Questions / Follow-Ups
1. Do we need composite indexes covering `is_archived` + `ingest_state`? Monitor query plans during T04/T05 before committing to extra indexes.
2. Should we materialize daily pipeline counts for dashboard instead of querying live? Currently out-of-scope; revisit if SaaS load dictates.
3. Confirm whether `source_type` (audio/document/text) requires dedicated index; preliminary assumption is no due to low cardinality.

## 9. Hand-off Notes
- This plan informs migration scripts + EF-06 repo changes. Record implemented indexes plus EXPLAIN outputs in status log once built.
- T04/T05 engineers should reference this document when shaping queries, ensuring they align with the indexed columns order and default filters.
