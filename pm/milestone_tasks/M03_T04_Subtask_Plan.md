# M03-T04 — Subtask Plan & Initial Test Matrix

_Date:_ 2025-12-09  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `M03_Taxonomy_Classification_Tasks_v1.1.md` defines T04 as aligning EF-07 taxonomy endpoints with `EF07_Api_Contract_v1.2.md`, covering CRUD for both Types and Domains plus soft/hard delete semantics.
- `EF07_Api_Contract_v1.2.md §8` already sketches shared fields and endpoint list, but lacks detailed payload validation rules, error codes, pagination behavior, capture-event hooks, and cross-links to EF-06 expectations (e.g., enforcing `{id,label}` pairs, `active` semantics). This task will expand the contract language and call out any additions to `EF07_EchoForgeApiAndUi_Spec_v1.1.md` if needed.
- EF-06 addendum §7 requires EF-07 to reject taxonomy mutations that would leave IDs without labels. EF-05 semantics also depend on EF-07 providing authoritative dropdown data so the semantic worker can align to canonical IDs.
- ETS governance mandates defining the test matrix before implementation; this plan enumerates the contract-level tests that EF-07 controllers and future API clients must satisfy.

## 2. Proposed Subtasks
1. ✅ **UT01 — Types Endpoint Contract Deep-Dive:** Document request/response models, validation (slug rules, uniqueness, `active` toggling), pagination/sorting for `GET /api/types`, and error scenarios. Capture in EF07 contract addendum and reference migrations.
2. ✅ **UT02 — Domains Endpoint Contract Mirroring:** Mirror UT01 for `/api/domains`, calling out differences (if any) and ensuring shared components avoid divergence.
3. ✅ **UT03 — Entry Update Expectations:** Specify how EF-07 entry create/update flows must accept taxonomy references (`{type_id,type_label}`, `{domain_id,domain_label}`), including rejection cases and capture-event logging requirements.
4. ✅ **UT04 — Observability & Governance Hooks:** Define required logging (`taxonomy.type.updated`, `taxonomy.domain.deleted`), INF-03 integration, and decision-log tie-ins for hard deletes/inactive transitions.
5. ✅ **UT05 — Test/ETS Coverage Definition:** Outline API contract tests, controller unit tests, and ETS scenarios verifying taxonomy CRUD, soft delete visibility, and resilience to dangling IDs.

## 3. Initial Test Coverage (Pre-Coding)
- **Contract Tests:** New suites under `tests/api/test_taxonomy_types.py` and `tests/api/test_taxonomy_domains.py` verifying 200/201/204 paths, validation failures (duplicate IDs, missing labels), and behavior when `active=false`.
- **Controller Unit Tests:** For the FastAPI/Flask layer (pending actual framework), ensure payload validation rejects ID-only or label-only inputs, enforces slug regex, and returns `EF07-INVALID-REQUEST` with detail fields.
- **Integration Smoke Tests:** End-to-end tests to create a taxonomy value, assign it to an entry (via EF-07 or admin script), deactivate it, and confirm entry responses still include both label and ID.
- **ETS Profiles:**
  - `ETS-API-TAX-01`: Exercises `GET/POST/PATCH/DELETE` for Types & Domains, verifying governance logging and dropdown filtering.
  - `ETS-DB-TAX-03`: (shared with T03) ensures EF-07 behavior stays aligned with EF-06 when taxonomy rows deactivate or delete.

## 4. UT01 — Types Endpoint Contract Details
- **Listing (`GET /api/types`):**
  - Optional pagination params (`page`, `page_size`) plus `sort_by`/`sort_dir`; defaults align with entries API.
  - Filter switches `active=true/false` for admin screens.
  - Response shape includes `items`, pagination metadata, and `last_updated_cursor` for cache invalidation.
- **Create/Update Validation:**
  - `id` must match slug regex `^[a-z0-9]+(?:[_-][a-z0-9]+)*$`, 3–64 chars.
  - `label` required; `name` optional but defaults to `id`.
  - Reject payloads missing label or attempting to change `id` on PATCH (`EF07-INVALID-REQUEST`).
  - Enforce uniqueness on `id`/`name`; duplicate results in `EF07-CONFLICT`.
- **Delete Semantics:**
  - `PATCH` toggles `active`; `DELETE` performs hard delete only when `allow_taxonomy_delete` config true; otherwise return `405`.
  - Responses include `deletion_warning` flag when entries still reference the ID (detected via EF-06 query), so UI can prompt operators.
- **Error Mapping:** Documented in EF07 contract §8 addendum; includes 404 when ID not found, 409 for slug clash, 422 for validation failure.

## 5. UT02 — Domains Endpoint Contract Details
- Domains reuse the same DTO module as Types; plan mandates a shared `TaxonomyPayload` schema with `kind` discriminator.
- Differences:
  - Domain IDs may be longer (64 chars) but share slug regex.
  - Responses include optional `metadata.parent_domain_id` placeholder for future hierarchy; currently must be null.
- Mirror all validation/error rules from UT01 to prevent drift; spec will reference a “shared behavior” section to avoid duplicate text.

## 6. UT03 — Entry Update Expectations
- EF-07 entry creation (capture) continues accepting `metadata.type_label`/`domain_label` only; however, UT03 defines the forward-compatible shape for future `/api/entries` PATCH:
  - Payload MUST send `{type_id, type_label}` pairs; ID-only or label-only rejected with `EF07-INVALID-REQUEST`.
  - When UI wants to clear taxonomy, both fields must be set to null; EF-07 emits `taxonomy.reference.cleared` capture event.
- Capture endpoints MAY include optional `taxonomy` block for advanced clients once EF-06 migrations are live; blueprint includes gating flag `enable_taxonomy_refs_in_capture`.
- EF-07 logs `taxonomy.reference.updated` events via INF-03 whenever IDs change; event payload matches EF-06 addendum requirements (`entry_id`, `field`, `old_id`, `new_id`, `label`).

## 7. UT04 — Observability & Governance Hooks
- **Logging:** INF-03 structured logs for each `POST/PATCH/DELETE` on taxonomy endpoints, capturing operator ID, payload summary, and resulting status.
- **Decision Records:** Hard delete attempts append entries to `pm/decisions/M03_taxonomy_delete_policies.md` (to be created) referencing M03-T12 once finalized.
- **Capture Events:**
  - `taxonomy.type.updated`, `taxonomy.type.deactivated`, `taxonomy.type.deleted` (parallel domain events) include metadata for ETS replay.
  - Events emitted synchronously after DB commit; failures bubble as 500 to keep audit trail consistent.
- **Metrics:** Add counters (`taxonomy_type_active_total`, `taxonomy_domain_active_total`) for Prometheus dashboards so governance can monitor churn.

## 8. UT05 — Detailed Test/ETS Coverage
- **API Contract Tests:**
  - `tests/api/test_taxonomy_types.py` cases: create success, duplicate ID conflict, invalid slug, deactivate/reactivate, delete with toggle disabled.
  - Domain suite mirrors types and adds test for metadata placeholder remaining null.
- **Controller/Service Unit Tests:**
  - Mock repository to ensure validation rejects half-populated payloads and slug mismatches.
- **Integration Smoke:** Verified via `tests/integration/test_taxonomy_entry_roundtrip.py` once EF-07 entry updates exist—ensures entry JSON includes IDs after taxonomy creation.
- **ETS:**
  - `ETS-API-TAX-01` expanded with phases for type and domain operations, verifying logs/events captured.
  - `ETS-DB-TAX-03` reuses EF-06 plan but now asserts EF-07 responses surface inactive IDs with warnings.

## 9. Open Questions / Assumptions
- EF-07 entry-edit endpoint timing remains TBD; UT03 language will flag it as future scope in the contract.
- Need final confirmation on whether taxonomy lists require pagination; plan currently documents optional pagination to stay future-proof.
- Governance must decide whether hard deletes require dual-operator approval; UT04 references decision doc stub pending M03-T12.

## 10. Next Steps
- Review and refine these subtasks with project owner; once approved, update `EF07_Api_Contract_v1.2.md` and supporting specs per UT01–UT04.
- Define concrete test cases and stubs before implementing EF-07 controllers (`M03-T05`).
- Ensure governance artifacts (decision log, capture events) reflect choices recorded under UT04/UT05.
