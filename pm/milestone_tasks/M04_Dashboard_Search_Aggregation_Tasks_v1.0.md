# M04 — Dashboards, Search & Aggregation — v1.0

---

## 0. Metadata

- **Milestone ID:** M04  
- **Milestone Name:** Dashboards, Search & Aggregation  
- **Version:** v1.0  
- **Scope Summary:**  
  Design and implement the read/insight layer for EchoForge:
  - Dashboard summaries over pipeline states and taxonomy  
  - Search and filter behavior for Entries  
  - Aggregation logic and EF-06 query patterns  
  - Alignment with EF07_Api_Contract_v1.2 (`/api/entries`, `/api/dashboard/summary`)  
  - ETS coverage for correctness and performance properties

M04 focuses on *reading and aggregating* from EF-06 and taxonomy tables; it does **not** change capture or pipeline mechanics.

- **Primary Components:**  
  - EF-06 EntryStore (querying & indexing)  
  - Taxonomy tables (`EntryType`, `EntryDomain`)  
  - EF-07 API (`/api/entries`, `/api/dashboard/summary`)  
  - UI dashboard surfaces (Electron/SPA)  
- **Governance:**  
  - Milestone_Task_Subsystem_v1.1.md  
  - EnaC_TestingSubsystem_v1.0.md  

---

## 1. Status Tracking Model

Each task contains a Status Block:

```markdown
- **Status:** pending  <!-- pending | in_progress | blocked | deferred | done -->
- **Last Updated:** —
- **Notes:** —
```

Codex-LLM MUST only mutate these three fields.

---

## 2. References

- `EchoForge_Architecture_Overview_v1.1.md`  
- `EchoForge_Component_Summary_v1.1.md`  
- `EF06_EntryStore_Spec_v1.1.md`  
- `EF06_EntryStore_Addendum_v1.2.md`  
- `EF07_Api_Contract_v1.2.md`  
- `M01_Capture_Ingress_Tasks_v1.1.md`  
- `M02_Processing_Pipeline_Tasks_v1.0.md`  
- `M03_Taxonomy_Classification_Tasks_v1.1.md`  

---

## 3. Tasks

---

### M04-T01 — Define Dashboard Use Cases & KPIs

- **Type:** design  
- **Depends On:** M01–M03  
- **ETS Profiles:** ETS-UX, ETS-Arch  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Enumerate the primary dashboard questions EchoForge v3 must answer, e.g.:

- “What’s flowing through the pipeline right now?”  
- “Where are things stuck?”  
- “What am I working on this week?”  
- “Which domains/types are most active?”  

Define v1.0 KPIs and visualizations, such as:

- Pipeline distribution (by `ingest_state`)  
- Recent Entries list (last N items)  
- Top Types / Top Domains (by count)  
- “Needs Review” slice (by `cognitive_status`)

Outputs:

- A short design note summarizing dashboard sections and metrics.  

---

### M04-T02 — Define Search & Filter Model for Entries

- **Type:** design  
- **Depends On:** M04-T01, EF07 v1.2  
- **ETS Profiles:** ETS-UX, ETS-API  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define how `/api/entries` should behave for:

- Free-text search (`q`) over title/summary/body/semantic fields.  
- Filters:
  - `type_id`, `domain_id`  
  - `pipeline_status` (ingest_state)  
  - `cognitive_status`  
  - `source_channel`  
  - `created_from` / `created_to`  

Decide:

- Whether filters are AND-combined (default), and how multiple values should be handled (e.g., comma-separated or repeated params).  
- Any default sort order (e.g., `updated_at desc`).

Outputs:

- A concise “Search & Filter Behavior” note referencing EF07 `/api/entries`.

---

### M04-T03 — Tune EF-06 Indexing for Dashboards & Search

- **Type:** implementation  
- **Depends On:** M04-T02, EF06 v1.2  
- **ETS Profiles:** ETS-DB, ETS-Perf  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define and implement required indexes in EF-06 and taxonomy tables for:

- `ingest_state` (pipeline distribution, filters)  
- `created_at`, `updated_at` (recency filters and sorts)  
- `type_id`, `domain_id` (taxonomy filters, dashboards)  
- Optional: text search index over `display_title`, `semantic_summary` (implementation-specific, e.g., PostgreSQL full-text).

Document:

- Any tradeoffs made for local vs SaaS deployments.  
- Expected query shapes from EF-07.

---

### M04-T04 — Implement `/api/dashboard/summary` Aggregation Logic

- **Type:** implementation  
- **Depends On:** M04-T01, M04-T03, EF07 v1.2  
- **ETS Profiles:** ETS-API, ETS-Perf  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement the backing logic for:

`GET /api/dashboard/summary`

using EF-06 and taxonomy tables to produce:

- Counts by `ingest_state`.  
- Top Types and Domains by Entry count.  
- Optional time-bounded slice (e.g., last 7 days), if included in M04-T01.

Ensure:

- Queries are efficient on expected dataset sizes.  
- Results format matches EF07 v1.2 examples.

---

### M04-T05 — Implement Search & Filtering for `/api/entries`

- **Type:** implementation  
- **Depends On:** M04-T02, M04-T03  
- **ETS Profiles:** ETS-API, ETS-DB  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement `/api/entries` semantics as defined in M04-T02:

- Honor query parameters (`q`, filters, sorting, pagination).  
- Ensure stable, predictable behavior when combining filters.  
- Respect taxonomy overlay semantics:
  - If `type_id` / `domain_id` reference a deleted taxonomy value, decision is whether to:
    - Still match entries that have that `type_id`, or  
    - Ignore deleted values in filter options.  
  Capture this behavior explicitly.

---

### M04-T06 — UI Wiring for Dashboard & Entry List (Electron/SPA)

- **Type:** implementation  
- **Depends On:** M04-T04, M04-T05, M03-T07  
- **ETS Profiles:** ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement the frontend wiring to:

- Call `GET /api/dashboard/summary` to render primary dashboard widgets.  
- Call `GET /api/entries` for main list views, with:
  - Type/Domain dropdown filters  
  - Pipeline status filters  
  - Search box tied to `q`  
  - Basic pagination controls.

This task is focused on wiring and correctness, not on pixel-perfect visual design; styling can evolve in later milestones.

---

### M04-T07 — (Optional) Saved Filters / Views Design

- **Type:** design (optional for v1.0)  
- **Depends On:** M04-T02  
- **ETS Profiles:** ETS-UX  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
If included in M04 scope, define how “saved views” should work:

- What persists (filter set, sort, search query).  
- Where settings are stored (local config vs DB table).  
- Whether views are global or user-specific.

Mark as *optional* and explicitly note whether implementation is deferred to a later milestone.

---

### M04-T08 — Implement ETS Cases for Dashboards & Search

- **Type:** test  
- **Depends On:** M04-T03, M04-T04, M04-T05  
- **ETS Profiles:** ETS-API, ETS-DB, ETS-Perf  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define and/or implement ETS test cases, including:

- Correctness of pipeline counts and taxonomy summaries in `/api/dashboard/summary`.  
- Filter combinations on `/api/entries` returning consistent, expected results.  
- Behavior with:
  - No taxonomy values defined.  
  - Some taxonomy values deactivated or deleted.  
- Basic performance expectations (e.g., queries over N entries complete within a reasonable time budget on reference hardware).

---

### M04-T09 — Generate Status Log for M04

- **Type:** governance  
- **Depends On:** At least some tasks in progress  
- **ETS Profiles:** —  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Create a status log entry under `pm/status_logs/` summarizing:

- Implementation progress for M04.  
- Any bottlenecks identified in dashboard/search design.  
- Decisions to defer optional features (e.g., Saved Views).

---

### M04-T10 — Capture Human Decisions (Search & Dashboard Philosophy)

- **Type:** governance  
- **Depends On:** M04-T01 through M04-T08  
- **ETS Profiles:** —  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Document under `pm/decisions/`:

- The role of dashboards in EchoForge v3 (quick triage vs deep analysis).  
- Any committed constraints on search semantics (e.g., always AND filters).  
- Decisions on optional features (Saved Views, pinned filters, etc.).  
- Any expected evolution for future milestones (e.g., semantic search, cross-entry thread views).

---

## 4. Exit Criteria

M04 is considered complete when:

1. Dashboard use cases and KPIs are documented and clearly scoped.  
2. EF-06 and taxonomy tables have indexes in place to support dashboard and search workloads.  
3. `/api/dashboard/summary` is implemented and returns correct, efficient aggregations.  
4. `/api/entries` supports the agreed search & filter model.  
5. The Electron/SPA client can display:
   - A functional dashboard using `/api/dashboard/summary`.  
   - A filterable/searchable Entries list backed by `/api/entries`.  
6. ETS tests validate correctness and basic performance characteristics for dashboards and search.  
7. M04 status log and decisions docs are created under `pm/`.  
