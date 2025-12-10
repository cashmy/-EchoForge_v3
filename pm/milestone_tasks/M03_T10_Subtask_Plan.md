# M03-T10 — Taxonomy ETS Coverage Plan

_Date:_ 2025-12-10  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `M03_Taxonomy_Classification_Tasks_v1.1.md` defines T10 as the execution arm for ETS validations covering API CRUD, EntryStore resilience, and EF-06 index behavior once M03-T05–T09 land.
- `EF07_Api_Contract_v1.2.md §3.4–3.5` specifies the Types/Domains payloads, header expectations (`X-Actor-*`), and delete-warning semantics that ETS suites must exercise end-to-end.
- `EF06_EntryStore_Addendum_v1.2 §7.4` and `EF06_EntryStore_Spec_v1.1 §3` require `entries.type_id/domain_id` indexes plus operator-friendly fallbacks when referencing IDs disappear; T09 delivered the indexes and helper scripts that T10 now needs to automate.
- `EnaC_TestingSubsystem_v1.0.md` + `EchoForge_Testing_Philosophy_v0.1.md` emphasize milestone-anchored, contract-level tests; taxonomy ETS profiles must therefore stay in `tests/ets` with runnable harness commands (`scripts/ets_runner.py --profile taxonomy`).
- MG06 governance file now tracks `MG06-TAX-IDX`; M03-T10 must provide executable evidence and documentation breadcrumbs so MG06 can reuse the same helpers without rediscovery.

## 2. Proposed Subtasks
1. ☑ **ST01 — Scenario Blueprint & Plan Doc**  
   - Capture this file plus scenario IDs (`ETS-API-TAX-01`, `ETS-DB-TAX-01..03`, `ETS-UI-TAX-01`, `ETS-DB-TAX-IDX-01`).  
   - Map each requirement bullet from T10 to concrete tests/helpers + acceptance evidence.
2. ☑ **ST02 — API CRUD & Soft-Delete ETS Cases**  
   - Extend the `ets_taxonomy` marker with FastAPI client tests covering create/list/update/delete for Types & Domains, actor metadata, and inactive filtering.  
   - Verify delete-warning payloads when `referenced_entries > 0` and ensure telemetry hooks fire.
3. ☑ **ST03 — Entry Resilience & Patch Scenarios**  
   - Build ETS tests showing entries retain taxonomy labels after deactivation/deletion and that patch flows emit the expected capture events / pending flags.  
   - Reuse `InMemoryEntryStoreGateway` + router overrides to keep scope self-contained.
4. ☑ **ST04 — Index Proof Harness**  
   - Refactor helper scripts under `scripts/` to allow env-driven DSNs and reusable functions.  
   - Add ETS test (skip when `ETS_TAXONOMY_DB_URL` undefined) that seeds sample entries, runs `EXPLAIN ANALYZE`, and asserts plans use `IDX_entries_type_id` / `IDX_entries_domain_type` while `pg_stat_user_indexes` records non-zero scans.
5. ☑ **ST05 — Documentation & Governance Updates**  
   - Update `tests/README.md`, milestone file, MI99/MG06 breadcrumbs as needed, and append status-log evidence summarizing ✅ ETS runs + warnings about DB prerequisites.  
   - Outline how MG06 should re-run the same profile, referencing helper scripts + env vars.

## 3. Scenario Catalog
| ID | Scope | Description | Evidence |
| --- | --- | --- | --- |
| ETS-API-TAX-01 | EF-07 API | Full CRUD round-trip for Types/Domains with actor headers, pagination, `active=false` toggles, delete warnings, and event/metric assertions. | `tests/ets/test_taxonomy_crud.py::test_ets_api_taxonomy_crud_flow` |
| ETS-API-TAX-02 | EF-07 API | Capture submission with taxonomy hints (flag enabled). | Existing `tests/ets/test_taxonomy_patch.py` + new resilience checks. |
| ETS-API-TAX-03..06 | EF-07 API | PATCH variations (reclassify, clear, label-only pending, feature-disabled block). | `tests/ets/test_taxonomy_patch.py` + new assertions linking to capture events.
| ETS-DB-TAX-01 | EF-06 DB | Entries referencing deactivated Types remain readable; API warns before delete. | New ETS test combining taxonomy + entry gateway. |
| ETS-DB-TAX-02 | EF-06 DB | Domains behave symmetrically (inactive rows still surface in dropdowns/entries). | Same module, domain-focused case. |
| ETS-DB-TAX-03 | EF-06/EF-07 | Entries survive taxonomy deletion; ETS ensures label fallback + patch clearing path logged. | ETS resilience test + status-log note. |
| ETS-DB-TAX-IDX-01 | EF-06 Performance | Postgres `EXPLAIN` & `pg_stat_user_indexes` confirm new indexes are used. | Env-aware ETS test invoking helper functions. |
| ETS-UI-TAX-01/02 | UI | (Tracked under T07 plan) – referenced for completeness; no new UI work here but ETS profile will note gating behavior. |

## 4. Deliverables Checklist
- [x] `tests/ets/test_taxonomy_crud.py` (or equivalent) with scenarios tied to IDs above.  
- [x] Enhanced `tests/ets/test_taxonomy_patch.py` coverage for pending-reconciliation + delete recovery paths.  
- [x] Env-aware helper functions in `scripts/seed_taxonomy_entries.py`, `scripts/collect_taxonomy_explain.py`, `scripts/show_index_scans.py` (+ `scripts/__init__.py`).  
- [x] New ETS index test using those helpers, skipped automatically when DB not configured.  
- [x] Documentation updates: `tests/README.md`, milestone file, MG06 + MI99 breadcrumbs, status log entry.  

## 5. Risks & Mitigations
- **Postgres availability:** Not all contributors have a seeded EF-06 database. → Tests will `pytest.skip` with clear instructions unless `ETS_TAXONOMY_DB_URL` or `DATABASE_URL` is set.  
- **Long-running seeding:** 2k-row seed script may slow suites. → Reuse `ON CONFLICT DO NOTHING` inserts and only reseed when needed; keep dataset modest.  
- **Feature-flag drift:** Patch ETS cases depend on `ENABLE_TAXONOMY_PATCH`. → Tests will explicitly set env vars per scenario.  
- **Overlap with MG06:** Avoid duplicating future governance work by referencing MG06 task IDs and making helpers reusable.

## 6. Next Steps
- Implement ST02–ST04 concurrently with code changes; keep ETS marker green via `scripts/ets_runner.py --profile taxonomy`.  
- Update milestone + status logs once suites run successfully and evidence captured.
