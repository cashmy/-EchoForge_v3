# M03-T06 — Entry Classification Update Mechanisms

_Date:_ 2025-12-10  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `M03_Taxonomy_Classification_Tasks_v1.1.md` defines T06 as the conceptual contract for how Entries are classified/reclassified using taxonomy overlays without introducing new EF-07 endpoints yet.
- `EF07_Api_Contract_v1.2.md §5.4` and §8 describe paired `{type_id,type_label}` / `{domain_id,domain_label}` semantics, capture-event expectations (`taxonomy.reference.updated|cleared`), and feature-flagged capture payloads.
- `EF06_EntryStore_Addendum_v1.2.md §7.2` clarifies that `type_id`/`domain_id` are nullable hints while labels remain the canonical human context; §7.6 dictates observability/metrics requirements for taxonomy touches.
- MG06 governance requires ETS-ready documentation of how operator actions change classification fields so that audit tooling can assert capture events plus INF-03 logs across entry mutations.

## 2. Proposed Subtasks
1. ☑ **ST01 — Capture Payload Blueprint**  
  Complete. §3.1 now documents the taxonomy payload, validation, persistence, and flag behavior for `/api/capture`.
2. ☑ **ST02 — Entry Patch Contract Draft**  
  Complete. §3.2 captures the PATCH request/response schema, validation, events, and metrics expectations.
3. ☑ **ST03 — Governance & Observability Notes**  
  Complete. §4 details logging, feature flags, reconciliation, and deletion handling requirements.
4. ☑ **ST04 — Test/ETS Matrix Stub**  
  Complete. §5 enumerates the automated test targets plus ETS scenarios and tooling hooks.

## 3. Payload Shape Notes

### 3.1 Capture Request Extension
Endpoint: `POST /api/capture`

Add optional `taxonomy` envelope:
```json
{
  "mode": "text",
  "source_channel": "manual_text",
  "content": "Idea about UI",
  "taxonomy": {
    "type": {
      "id": "project_note",
      "label": "Project Note"
    },
    "domain": {
      "id": null,
      "label": "Product Ops"
    }
  }
}
```

Behavior/constraints:

1. **Feature Flag** — INF-01 setting `enable_taxonomy_refs_in_capture` controls enforcement.
   - `false` (default): request MAY include the object, but EF-07 validates format then drops it (no-op) for backward compatibility.
   - `true`: payload is validated and, when IDs resolve, persisted to EF-06 alongside the existing `type_label`/`domain_label` fields.
2. **Validation**
   - When `taxonomy.type` or `.domain` is present, both `id` and `label` must be supplied unless the caller explicitly sends `{ "id": null, "label": null }` to indicate "label-only" capture.
   - `id` follows the slug regex from EF-07 taxonomy APIs; `label` must be a non-empty string when provided.
   - Mixed submissions (`id` provided but `label` missing) raise `422 EF07-INVALID-REQUEST` with `details.field = "taxonomy.type.label"` (or `.domain.label`).
3. **Persistence Rules**
   - If an `id` resolves to an active taxonomy row, EF-01/EF-06 store both ID and label; otherwise we store only the provided label and set `id` to `null`.
   - Capture events:
     - `taxonomy.reference.pending` when label-only submissions occur (signals reconciliation backlog).
     - `taxonomy.reference.updated` when both ID and label are persisted during capture.
4. **Response Echo** — `/api/capture` responses include a `taxonomy` block mirroring what was stored (IDs normalized, labels trimmed) so clients can reconcile immediately.
5. **Security/Governance** — Actor metadata is inherited from capture auth context; INF-03 logs include `source_channel`, `taxonomy_dimension`, and `pending_reconciliation` flag for governance review.

### 3.2 Entry Classification PATCH Blueprint
Endpoint (future): `PATCH /api/entries/{entry_id}` — extends EF07 §4.3 partial update contract.

#### Request Schema (delta-style)
```json
{
  "taxonomy": {
    "type": {
      "id": "project_note",
      "label": "Project Note"
    },
    "domain": {
      "id": null,
      "label": null,
      "clear": true
    }
  },
  "expected_version": 17
}
```
- `taxonomy` block is optional; when absent we ignore classification entirely.
- Each node accepts fields `id`, `label`, `clear`. If `clear` is `true`, both `id` and `label` MUST be `null` or omitted.
- `expected_version` (mirrors existing optimistic-lock semantics) equals the Entry’s `revision`/`version`. On mismatch return `409 EF07-CONFLICT` with `details.reason = "version_mismatch"`.

#### Validation & Error Modes
1. **Paired Fields** — If either `id` or `label` is non-null, both must be supplied (same rule as capture). Violations return `422 EF07-INVALID-REQUEST` with `details.field` pointing to the missing counterpart.
2. **No-Op Filtering** — Requests identical to stored state (same IDs & labels, no clear flag) return `204` with `taxonomy.no_change = true` in the body to help clients skip redundant auditing.
3. **Cross-Dimension Independence** — `taxonomy.type` and `.domain` are validated independently so clients can update one dimension without resubmitting the other. Only touched dimensions emit events.
4. **Inactive IDs** — If supplied `id` references an inactive taxonomy row, write proceeds but response attaches `deletion_warning = { "dimension": "type", "reason": "inactive" }`. Governance layer logs severity `warn`.
5. **Label-Only Writes** — Allowed when IDs are unknown. Server trims/normalizes labels, persists `null` ID, sets `reconciliation_pending = true` for that dimension, and surfaces `pending_reconciliation` in the response payload.

#### Response Blueprint
```json
{
  "entry_id": "ent_123",
  "version": 18,
  "taxonomy": {
    "type": {
      "id": "project_note",
      "label": "Project Note",
      "pending_reconciliation": false
    },
    "domain": {
      "id": null,
      "label": null,
      "pending_reconciliation": false
    }
  },
  "deletion_warning": null,
  "taxonomy_no_change": false
}
```
- `version` reflects the post-write revision so clients can chain updates.
- `taxonomy_no_change = true` only when validation succeeded but no mutation occurred (handy for UI toggles).

#### Events, Logging, Metrics
1. **Capture Events**
   - `taxonomy.reference.updated` emitted per dimension when values change; payload includes `{entry_id, dimension, from_id, from_label, to_id, to_label, actor}`.
   - `taxonomy.reference.cleared` when `clear` or null pair removes data; includes previous state snapshot.
2. **INF-03 Logs** — structured entry `taxonomy_patch` with `entry_id`, `dimension`, `action` (`update|clear|noop`), `actor_id`, `actor_source`, `pending_reconciliation` bool, and `expected_version` to satisfy MG06 traceability.
3. **Metrics**
   - `taxonomy_patch_attempt_total{dimension}` increments for every request referencing that dimension.
   - `taxonomy_patch_conflict_total` increments on version mismatches.
   - `taxonomy_reconciliation_pending` gauge increments when label-only writes occur, decrements once reconciliation jobs backfill IDs.

#### Security & Authorization
- Reuse EF07 role `entries:mutate_taxonomy`. Admin/Triage personas only. Enforcement performed before validation to avoid leaking entry existence.
- Requests must include `actor_id` + `actor_source` headers (already required for admin APIs); these propagate into events/logs unchanged.

#### Client Guidance
- Always GET entry details first to fetch current `version` and taxonomy snapshot, then PATCH with deltas. Bulk reclassification flows should batch per dimension to avoid conflicts.
- When clearing, prefer `{"clear": true}` for readability; server treats `{"id": null, "label": null}` equivalently.
- Consumers listening to WebSocket/Push channels receive `entry.taxonomy.changed` notifications keyed by `entry_id` so dashboards refresh promptly.

## 4. Governance & Observability Considerations
### 4.1 Event + Log Requirements
- Every classification mutation (capture-time or PATCH) must:
  - emit capture events with before/after deltas, actor metadata, and whether the taxonomy row is active.
  - log structured entries via INF-03 with `entry_id`, `taxonomy_dimension`, `action`, `actor`, `referenced_entries`.
- Logs follow INF-03 message key `taxonomy_mutation` and include:
  - `action_source`: `capture`, `patch`, or `reconciliation`.
  - `feature_flag_state`: snapshot of `enable_taxonomy_refs_in_capture` + future `enable_taxonomy_patch` toggles for MG06 audits.
  - `audit_pointer`: link to capture event ID so ETS tooling can correlate.

### 4.2 Config + Feature Flags
- Config service exposes two toggles:
  1. `enable_taxonomy_refs_in_capture` (existing) — controls request parsing; logging still fires even when persistence is disabled so governance can verify attempted usage.
  2. `enable_taxonomy_patch` (new) — wraps admin PATCH endpoint. When disabled, API responds `403 EF07-FEATURE-DISABLED` and logs a `taxonomy_mutation` entry with `action="rejected"`.
- Both flags must be queryable via INF-01 runtime snapshot so ETS harnesses can assert correct state before running scenarios.

### 4.3 Reconciliation + Jobs
- When capture ingestion supplies labels lacking IDs, reconciliation jobs (per EF06 §7.6) enqueue `taxonomy.reference.updated` after IDs backfill, with `changes.source = "reconciliation"`.
- Job payloads carry `pending_duration_ms` to measure SLA; INF-02 metrics emit `taxonomy_reconciliation_age_seconds` histogram for MG06.
- Reconciliation outcomes log `tax_recon_result` entries that cite the original capture/patch event IDs for lineage.

### 4.4 Deletion/Deactivation Handling
- Hard deletes must not cascade; if an entry references an inactive/deleted taxonomy ID, UI clients rely on stored labels plus `deletion_warning` hints.
- When admins deactivate a taxonomy row, EF05 pushes `taxonomy.reference.stale` events used by dashboards to highlight impacted entries; MG06 expects evidence this signal reaches INF-03 logs within 60s.
- Clearing classifications through PATCH is the canonical way to resolve stale references; reconciliation jobs only backfill IDs—they never remove labels.

## 5. Test & ETS Alignment
### 5.1 Automated Test Surfaces
- **Unit** — extend `tests/unit/test_capture_api.py` (capture payload) and add `tests/unit/test_entry_patch_taxonomy.py` covering optimistic locks, clear flag, and reconciliation markers.
- **Service** — update `tests/unit/test_taxonomy_service.py` to ensure reconciliation hooks set pending flags + metrics.
- **API/Contract** — create `tests/api/test_entries_taxonomy_patch.py` validating paired-field enforcement, deletion warnings, no-op responses, and auth errors.

### 5.2 ETS Matrix (MG06)
| Scenario | Description | Preconditions | Assertions |
| --- | --- | --- | --- |
| ETS-API-TAX-02 | Capture submission with taxonomy hints | `enable_taxonomy_refs_in_capture=true` | Entry detail echoes taxonomy block, `taxonomy.reference.updated` event logged, INF-03 record includes feature flag snapshot |
| ETS-API-TAX-03 | Reclassify via PATCH | Feature flag on, entry initially classified | Response carries new version, event/log pairs recorded, metrics increment `taxonomy_patch_attempt_total` |
| ETS-API-TAX-04 | Clear classification via PATCH | Entry has both dimensions set | `taxonomy.reference.cleared` emitted, response `pending_reconciliation=false`, log action `clear` |
| ETS-API-TAX-05 | Label-only write pending reconciliation | Domain ID unknown | Response `pending_reconciliation=true`, gauge increments, reconciliation job later flips flag and emits `taxonomy.reference.updated` |
| ETS-API-TAX-06 | Feature flag disabled rejection | `enable_taxonomy_patch=false` | API returns `403` with feature-disabled code, INF-03 log action `rejected`, no DB writes |

### 5.3 Tooling Hooks
- `scripts/ets_runner.py` gains `--profile taxonomy-classification` to orchestrate the above scenarios with proper flag toggling via INF-01 APIs.
- ETS harness captures Kafka/event payloads plus log lines, linking them via `audit_pointer` to satisfy MG06 evidence packets.
- Add MG06 documentation snippet referencing these cases under `pm/milestone_tasks/MG06_Testing_ETS_Governance_v1.1.md` once tests exist.
