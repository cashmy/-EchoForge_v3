# Decision: Taxonomy Naming, Delete Policy, and UI Treatment

_Date:_ 2025-12-10  
_Author:_ GPT-5.1-Codex  
_Linked Tasks:_ M03-T12, M03 milestone exit criteria  
_Status:_ Accepted

## Context
M03 delivered the taxonomy foundations across EF-06 (EntryStore schema/indexes), EF-07 (Types/Domains API), and the UI surfaces/ETS coverage. The remaining governance item (T12) requires codifying how operators should name taxonomy rows, when DELETE is appropriate, and how the UI treats inactive/deleted references going forward.

## Decisions
1. **Naming conventions**  
   - `id` fields MUST be lowercase slug strings (enforced by API validation) and SHOULD encode the type/domain intent succinctly (e.g., `architecture_note`, `platform_ops`).  
   - `name` mirrors `id` unless a shorthand code is needed; when provided, use PascalCase or SCREAMING_SNAKE so dropdowns can display human-friendly labels while power users reference the code.  
   - `label` is the operator-facing string (sentence case) and can be adjusted without changing the `id`.

2. **Delete policy**  
   - Hard `DELETE` remains available but is intended for rare cleanup scenarios (e.g., test data or erroneous rows).  
   - Default practice is to set `active = false` (soft delete) so historical entries retain their taxonomy IDs/labels and UI dropdowns can optionally include inactive rows.  
   - When hard delete occurs, the API returns `referenced_entries` and warnings; EntryStore retains the last known `type_label`/`domain_label` so entries remain readable.  
   - Operations teams MUST log any hard deletes in runbooks/status logs for auditability.

3. **UI treatment of inactive/deleted values**  
   - Capture UI hides taxonomy assignment unless `enable_taxonomy_refs_in_capture` is flipped on; when enabled, dropdowns list active rows by default and can optionally reveal inactive ones (tagged with an “inactive” chip).  
   - Entries referencing inactive/deleted IDs display badges explaining the state (e.g., “Type archived”).  
   - Editing an entry with a deleted taxonomy requires reclassification; patch APIs log `taxonomy.reference.cleared` events to keep timeline context.

4. **Future hierarchy/tagging**  
   - Hierarchical domains / tag systems remain out of scope for M03.  
   - A future milestone MAY revisit this once capture workflows stabilize; until then, metadata fields like `metadata.parent_domain_id` remain reserved and the API rejects attempts to set them.

## References
- `EF07_Api_Contract_v1.2.md §3.4–3.5` — validation + delete warning behavior.  
- `EF06_EntryStore_Addendum_v1.2 §7` — EntryStore fields and index strategy.  
- `pm/milestone_tasks/M03_T07_Subtask_Plan.md` — UI behavior/feature flags.  
- `tests/ets/test_taxonomy_crud.py`, `test_taxonomy_patch.py`, `test_taxonomy_db_indexes.py` — executable evidence.

## Follow-Up Actions
- Update `pm/milestone_tasks/M03_Taxonomy_Classification_Tasks_v1.1.md` (T12 section) to link this decision.  
- Ensure MG06 + MI99 entries reference this note when taxonomy governance questions arise.
