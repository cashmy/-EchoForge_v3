# M03-T02 — Subtask Plan & Initial Test Matrix

_Date:_ 2025-12-09  
_Owner:_ GPT-5.1-Codex  
_Milestone:_ M03 — Taxonomy & Classification Layer

## 1. Research Summary
- `M03_Taxonomy_Classification_Tasks_v1.1.md` requires the Domain taxonomy to mirror Types (flat list, advisory references) with `id`, `name`, `label`, `description`, `active`, `sort_order`, and timestamps.
- `EF06_EntryStore_Spec_v1.1.md` already defines a `domain_labels` table (UUID-based) but lacks canonical slug guidance, soft-delete semantics, or optional FK references in `entries`. The v1.2 addendum now covers Types (§7); Domains must be added for parity.
- `EF05_GptEntrySemanticService_Spec_v1.0.md` and the semantic worker expect to persist `domain_label` outputs today. Introducing `domain_id` requires analogous handling to `type_id` so UI filters and EF-07 endpoints stay consistent.

## 2. Proposed Subtasks
1.✅ **SD01 — Domain Schema Addendum:** Extend `EF06_EntryStore_Addendum_v1.2.md` with a `entry_domains` table definition (slug ID, unique name, label, description, active flag, sort order, metadata, timestamps) and note how it maps to legacy `domain_labels`.
2. ✅ **SD02 — Entry References & Soft Delete Semantics:** Define `domain_id` column behavior in `entries`, including orphan handling, label fallbacks, and UI expectations when a domain is deactivated/deleted.
3. ✅ **SD03 — Migration Blueprint:** Outline migration sequencing for introducing `entry_domains` + `domain_id`, seeding starter domains, and ensuring EF-05/EF-07 remain backward compatible during rollout.
4. ✅ **SD04 — EF-07 API Alignment:** Specify payload/validation rules for `/api/domains` endpoints (GET/POST/PATCH/DELETE) so they map cleanly to the schema. Call out how `active`/`sort_order` control UI dropdowns.
5. ✅ **SD05 — Observability & Governance Hooks:** Added mirrored requirements for Domains (capture events, metrics, ETS mapping, delete gating) to `EF06_EntryStore_Addendum_v1.2.md §7.6`, ensuring API/service work inherits the same controls as Types.

## 3. Initial Test Coverage (Pre-Coding)
- **Unit — Entry Store Gateway:** Add tests ensuring domain CRUD operations enforce uniqueness, default `active=True`, and respect `sort_order`. Validate the ability to set `domain_id` on entries and keep the label when ID is missing.
- **Unit — Semantic Worker:** Expand `tests/unit/test_semantic_worker.py` to cover classification outputs that include domain IDs, guaranteeing EF-05 persists both `domain_id` and `domain_label` (or only the label when ID missing).
- **API Contract Tests:** Plan new tests (future `tests/api/test_taxonomy_domains.py`) covering the `/api/domains` lifecycle, particularly `active=false` behavior and DELETE semantics.
- **ETS Scenario:** Draft `ETS-DB-TAX-02` scenario that seeds domains, assigns them to entries, deactivates a domain, and confirms UI/API flows still show linked entries via labels.

## 4. Open Questions / Assumptions
- Domain IDs follow the same slug rules as Types; naming conventions will be finalized under M03-T12.
- No hierarchy in v1.1; future parent-child relationships would require an addendum.
- Assume no automatic backfill of historical entries; operators will map existing `domain_label` values later via EF-07.

## 5. Next Steps
- Incorporate the subtasks into the M03 milestone checklist (Section 3) and mark M03-T02 as `in_progress`.
- Begin SD01 by extending the EF06 addendum with the domain schema + references before proceeding to migrations and API alignment.
