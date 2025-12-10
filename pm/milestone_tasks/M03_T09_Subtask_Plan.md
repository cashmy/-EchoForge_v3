# M03-T09 — Taxonomy Indexing Plan

_Date:_ 2025-12-10  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `EF06_EntryStore_Spec_v1.1.md §3` already recommends indexes on `domain_label` + `type_label`; this task formalizes them using the new `type_id` / `domain_id` columns introduced during M03-T03.
- `EF06_EntryStore_Addendum_v1.2 §7.4` callouts describe projected dashboard queries (filtering Entry lists by taxonomy) and require sub-second response for 100k-row datasets.
- `EF07_EchoForgeApiAndUi_Spec_v1.1 §5` states the dashboard and capture consoles will filter by taxonomy on every refresh and rely on EntryStore pagination endpoints.
- `MG06_Testing_ETS_Governance_v1.1 §4.2` mandates proof that DB migrations tied to governance features run safely (concurrent builds, rollback notes, evidence of analyze/vacuum as needed).
- Operational telemetry from development shows `entries` scans already approach tens of milliseconds per query without indexes at ~5k rows; extrapolated to prod-scale data this would become a bottleneck.

## 2. Proposed Subtasks
1. ☑ **ST01 — Migration Blueprint**  
   - Draft migration plan covering concurrent index creation (`CREATE INDEX CONCURRENTLY`) and rollback notes.  
   - Identify precise column order (`type_id`, `domain_id`, composite) and naming (`IDX_entries_type_id`, `IDX_entries_domain_id`).
2. ☑ **ST02 — Implement Alembic Migration**  
   - Add migration file plus unit test stub verifying metadata reflection picks up new indexes.  
   - Ensure offline migrations (for packaging) include `op.create_index(..., postgresql_concurrently=True)` guards.
3. ☑ **ST03 — Spec & Config Documentation**  
   - Update `EF06_EntryStore_Spec_v1.1.md` (or addendum) to list the new indexes and describe expected query shapes.
4. ☑ **ST04 — Query Validation & Benchmarks**  
   - Captured `EXPLAIN ANALYZE` output before/after on representative queries (`SELECT ... WHERE type_id = :id` and combined filters).  
   - Stored snippets under `pm/status_logs/Status_Log_M03_2025-12-10.md` as evidence with helper script references.
5. ☑ **ST05 — ETS/Test Hooks**  
   - Extended ETS plan to include regression ensuring filters hit indexes (check `idx_scan` metrics via `pg_stat_user_indexes`).  
   - Added smoke-test blueprint (pytest + helper scripts) and documented MG06 + MI99 breadcrumbs for future automation.

## 3. Implementation Notes
- **Index Choices:**
  - `IDX_entries_type_id` on `(type_id)` for equality filters and counts.  
  - `IDX_entries_domain_id` on `(domain_id)` for symmetry.  
  - Optional composite `IDX_entries_domain_type` on `(domain_id, type_id)` retained for combined filters (already recommended for labels; confirm whether label-based index should be repurposed or duplicated for IDs).
- **Null Handling:** Most entries will have `NULL` IDs initially; Postgres will skip nulls efficiently, so no partial index is required yet. Revisit if storage overhead grows.
- **Migration Safety:**
  - Use `op.create_index(..., postgresql_concurrently=True)` and guard `context.is_offline_mode()` to avoid offline failures.  
  - Document manual fallback for environments without `CONCURRENTLY` support (SQLite dev profiles) by wrapping statements in feature checks.
- **Rollback Plan:** Provide `op.drop_index` statements in downgrade; ensure names match exactly.

## 4. Test & Validation Matrix
| ID | Scenario | Tooling | Expected Evidence |
| --- | --- | --- | --- |
| IDX-01 | Create indexes via Alembic upgrade | `pytest tests/unit/test_migrations.py` (new) | Migration succeeds locally with Postgres container, indexes visible via `pg_indexes`. |
| IDX-02 | Dashboard filter query uses index | `scripts/collect_taxonomy_explain.py` + status log snapshot | Query shows `Index Scan using idx_entries_type_id`. |
| IDX-03 | ETS audit of `pg_stat_user_indexes` | MG06 ETS extension (`MG06-TAX-IDX`) | Report includes non-zero `idx_scan` counts for new indexes after simulated workload. |
| IDX-04 | Rollback safety | `alembic downgrade` dry-run | Downgrade drops indexes cleanly without locking errors. |

## 5. Deliverables Checklist
- [x] Migration file under `backend/migrations/versions/` creating indexes with concurrent option.  
- [x] Updated EF06 spec/addendum excerpt with new index names.  
- [x] Status log entry summarizing benchmark deltas.  
- [x] ETS/test notes referencing IDX scenarios (see §§9–10 plus MG06/MI99 breadcrumbs).  
- [ ] Optional helper script (`scripts/db/show_taxonomy_index_usage.py`) if ops wants visibility (stretch).  

## 6. Risks & Mitigations
- **Long build time on large tables:** Mitigate using concurrent build and scheduling migration during low-traffic windows.  
- **Write amplification:** Monitor `pg_stat_bgwriter`/`pg_stat_user_tables` after rollout; if insert cost spikes, reassess necessity of both indexes.  
- **SQLite dev parity:** Document that dev profile (SQLite) skips index creation or uses equivalent statements; ensure code paths that expect indexes remain resilient.

## 7. Next Steps
- Complete ST01 blueprint doc snippets (this file).  
- Begin ST02 migration implementation in backend repo.  
- Coordinate with MG06 owner for ETS instrumentation once indexes land.

## 8. ST01 — Detailed Blueprint (2025-12-10)

1. **Indexes to Create**  
   - `IDX_entries_type_id` on `entries(type_id)` (btree).  
   - `IDX_entries_domain_id` on `entries(domain_id)` (btree).  
   - `IDX_entries_domain_type` on `entries(domain_id, type_id)` to mirror combined filter usage; existing label-based index will remain for backward compatibility until ID adoption is universal.
2. **Creation Strategy**  
   - Use Alembic migration with `op.create_index(..., postgresql_concurrently=True)` when `context.is_offline_mode()` is false.  
   - For offline migrations (packaged installers / SQLite dev), skip concurrent flag and fall back to standard `CREATE INDEX` guarded by dialect checks to avoid unsupported syntax.
3. **Lock/Timing Considerations**  
   - Run migrations during maintenance windows; `CONCURRENTLY` prevents exclusive locks but still acquires brief SHARE locks.  
   - Document requirement to disable other schema changes while indexes build.
4. **Rollback Plan**  
   - Downgrade step drops indexes via `op.drop_index("IDX_entries_type_id", table_name="entries")`, same for others.  
   - Note that Postgres retains index storage until VACUUM; advise ops to run `VACUUM ANALYZE entries` after downgrade if the indexes are removed.
5. **Verification Checklist**  
   - After upgrade, run `SELECT indexname FROM pg_indexes WHERE tablename='entries';` to confirm presence.  
   - Execute `EXPLAIN` on `SELECT id FROM entries WHERE type_id = 'seed-type-1' LIMIT 10;` to ensure `Index Scan` plan.  
   - Record these steps in status log as evidence.

## 9. ST04 — Benchmark Evidence (2025-12-10)

- Seeded 2,000 synthetic entries via `scripts/seed_taxonomy_entries.py` (balanced across four types × four domains).  
- `scripts/collect_taxonomy_explain.py` captured representative plans:
   - `type_only` query uses `Index Scan using "IDX_entries_type_id"` with total execution time `0.34 ms`.
   - `domain_only` query hits `Index Scan using "IDX_entries_domain_type"` with execution time `0.25 ms`.
   - Combined filter uses the composite index with execution time `0.06 ms`.
- `scripts/show_index_scans.py` reports `idx_scan` counts (after single benchmark run):
   - `IDX_entries_domain_id: 0` (not yet exercised; future tests will include domain-only workloads).
   - `IDX_entries_type_id: 1`, `IDX_entries_domain_type: 2`, confirming Postgres recorded index usage.  
- Evidence pasted into `pm/status_logs/Status_Log_M03_2025-12-10.md` per ST04 requirement, referenced by `M03_T09_Subtask_Plan.md` and MG06 task breadcrumb.

## 10. ST05 — ETS/Test Hooks (2025-12-10)

- **Automated helper scripts**: `scripts/show_index_scans.py` captures `pg_stat_user_indexes` metrics per index; `scripts/collect_taxonomy_explain.py` can be reused inside ETS harnesses to assert plan shape.  
- **MG06 ETS alignment**: filed test case stub `ETS-DB-TAX-IDX-01` (documented in `pm/milestone_tasks/MG06_Testing_ETS_Governance_v1.1.md`) that runs workload, checks `idx_scan` > 0 for each taxonomy index, and archives the helper script output as evidence.  
- **MI99 follow-up**: `pm/milestone_tasks/MI99_Edge_Case_Backlog_v1.0.md` now tracks `MI99-T14` to ensure ETS harness adoption does not regress once MG06 begins.  
- **CI smoke coverage**: plan to add a lightweight pytest (`tests/unit/test_taxonomy_indexes.py`) that seeds ~200 rows via fixtures, runs the same EXPLAIN queries, and asserts the plan text includes the expected `Index Scan using` string (guards with `pytest.mark.postgres`).  
- **Governance logging**: status log now references the scripts + evidence so auditors know how to reproduce results; helper script outputs are archived alongside `Status_Log_M03_2025-12-10`.  
- **Next hook**: once MG06 ETS harness is active, wire these scripts into its setup/teardown to produce machine-readable artifacts uploaded alongside ETS reports.
