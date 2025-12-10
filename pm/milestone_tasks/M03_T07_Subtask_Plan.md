# M03-T07 — UI Taxonomy Retrieval Enablement

_Date:_ 2025-12-10  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `M03_Taxonomy_Classification_Tasks_v1.1.md` defines T07 as wiring EF-07 Types/Domains GET endpoints into the desktop UI so capture/edit/filter experiences surface authoritative taxonomy lists.
- `EF07_Api_Contract_v1.2.md §3.4` (Types) and §3.5 (Domains) specify payloads, pagination, and `active` semantics; §8 reiterates how inactive IDs must stay visible when referenced by existing entries.
- `EF07_DesktopHostAdapter_Spec_v0.1.md §4` outlines how the Electron shell consumes EF-07 APIs via the local gateway and caches bootstrap data for offline-aware dropdowns.
- `EF06_EntryStore_Addendum_v1.2 §7` notes that entries can reference inactive or deleted taxonomy IDs, so the UI must still render stored labels even when `active=false` from GET responses.
- `MG06_Testing_ETS_Governance_v1.1` expects ETS evidence proving that feature flags, dropdown hydration, and inactive taxonomy labeling behave consistently across admin and operator roles.

## 2. Proposed Subtasks
1. ☑ **ST01 — API/Data Access Blueprint**  
   Implemented via `frontend/src/api/taxonomy.ts` which standardizes `/api/types` + `/api/domains` fetch parameters and pagination.
2. ☑ **ST02 — Desktop Data Store & Feature Flags**  
   `frontend/src/state/useTaxonomyStore.ts` now persists taxonomy lists in Zustand with localStorage cache + feature flag gate from `/api/healthz`.
3. ☑ **ST03 — UI Integration States**  
   `frontend/src/components/TaxonomyConsole.tsx` introduces dropdowns, inactive chips, custom labels, and dashboard badges consuming the shared store.
4. ☑ **ST04 — Governance, Logging & Metrics Hooks**  
   Store + UI emit telemetry events (`window.dispatchEvent` + console) and surface load errors, stale cache states, and flag-driven read-only warnings.
5. ☑ **ST05 — Validation & Test Matrix**  
   Added `frontend/src/state/useTaxonomyStore.test.ts` (Vitest) plus npm `test` script to cover cache hydration + refresh flows; ETS extension documented here pending automation.

## 3. API/Data Retrieval Strategy

### 3.1 Request Parameters & Pagination
- Use `GET /api/types?active=true` for default dropdown hydration; include `active=false` only for admin CRUD surfaces to limit payloads.
- Domains follow the same contract. Cache `next_page_token` in case the catalog grows; initial implementation can request `page_size=200` but must handle `has_more=true` with iterative fetches.
- Stamp each fetch with `fetched_at` and `etag` (if provided) to support conditional refresh later.

### 3.2 Caching & Refresh
- Desktop host adapter loads taxonomy lists during bootstrap (after auth) and stores them in the shared data store with `status = idle|loading|error`.
- Provide a `refreshTaxonomy()` IPC action that clears cache + re-fetches so admins can pull the latest list after CRUD changes.
- For offline mode, keep the last-known-good payload serialized in `appData/taxonomy-cache.json`; check version hash before reusing it.

### 3.3 Error Handling & Offline Fallbacks
- If GET fails (network/403), UI should show a warning banner plus fallback to previously cached values; capture event `ui.taxonomy.dropdown_error` with `error_code` and `actor_id`.
- If no cached data exists, disable taxonomy pickers and show a CTA linking to troubleshooting docs.

## 4. UI Interaction Contracts

### 4.1 Entry Capture / Edit Forms
- **Dropdown population:** use cached Types/Domains sorted by `sort_order`, then `label`.
- **Inactive values:** if an entry references `type_id` not marked `active`, still render it with a "(inactive)" chip and allow clearing or replacement.
- **Custom labels:** provide "Add custom label" that toggles a free-form text input; when used, set `type_id=null` but preserve the label.
- **Validation:** enforce paired `id`/`label` rules client-side before POST/PATCH requests, mirroring T06 blueprint semantics.

### 4.2 Dashboard Filters & Badges
- Filters default to active IDs only; add a toggle "Include inactive" for audit scenarios.
- Display taxonomy badges on cards/lists showing both label and optional domain color chip.
- When filters include IDs no longer present, show them in a "Legacy filters" section with tooltip guidance to reclassify entries.

### 4.3 Admin CRUD Screens
- After an admin updates taxonomy, automatically trigger `refreshTaxonomy()` so operators see changes without app restart.
- Show counts of entries referencing each Type/Domain (requires new API or reuse `aggregate=true` once available) to highlight safe deactivation.

## 5. Governance, Telemetry, and Feature Flags
- UI should log via INF-03 whenever taxonomy data fails to load, takes >3s, or is older than configurable threshold (default 10 minutes).
- Metrics to increment: `taxonomy_dropdown_load_total{status}` with `status=success|failed|stale_cache`.
- Respect `enable_taxonomy_refs_in_capture`: flag now defaults to **false** in `config/profiles/{dev,desktop}.yaml`; when unset or disabled the SPA hides the console body, surfaces a governance notice, and keeps the status card badge/telemetry active so operators still see stored values without interacting with draft UI.
- Record MG06 evidence steps: screenshot of dropdown with inactive chip, log excerpt, and ETS run ID once automated tests execute.

## 6. Test & ETS Coverage Plan
- **Unit/Component**: React/Vue component tests ensuring dropdown renders active + inactive, handles custom labels, and calls refresh on admin action.
- **Integration/Playwright**: simulate offline cache path, verifying fallback data loads and warning banner appears.
- **ETS (new profile extension)**: add `ETS-UI-TAX-01` scenario orchestrating capture/edit flows with taxonomy preloaded, verifying INF-03 logs and metrics; add `ETS-UI-TAX-02` for inactive chips.
- **Manual checklist**: include steps for toggling feature flag, refreshing cache, and verifying watchers still capture taxonomy labels when dropdown hidden.

## 7. Current Status — 2025-12-10

- Taxonomy console shipped behind the `enable_taxonomy_refs_in_capture` feature flag and is **hidden by default** (see `frontend/src/App.tsx` and `DashboardPage.tsx`).
- Dashboard now shows a placeholder card explaining how to re-enable the UI plus the Runtime Snapshot badge reporting the flag state.
- Healthcheck feature flags drive both the data store and UI decision helpers; Vitest cache tests remain green with the new defaults.
- Next unblock to expose the console is aligning capture workflow readiness; no additional code changes required once the flag flips on.
