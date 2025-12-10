# MG06 — Testing, ETS Integration & Governance — v1.1  
## (Governance Milestone — Not a Build Milestone)

---

## ⚠ Purpose Clarification (Critical)

This milestone is a **Governance Milestone**, not part of the feature‑development sequence.

All functional components, schema definitions, migrations, API behavior, UI structures,  
and runtime logic MUST already be implemented before MG06 begins.

**MG06 performs system‑level consolidation only:**

- Consistency validation  
- Governance alignment  
- Drift detection  
- Test-layer definition  
- Test‑tooling integration  
- System‑wide correctness checks  

Codex‑LLM MUST NOT reinterpret or modify earlier milestones based on tasks here.

---

## 🔍 Drift Check

Before executing any task, Codex‑LLM MUST confirm:

- No new functional features are introduced here  
- No schema changes occur  
- No architectural ordering changes are attempted  
- No milestone re‑sequencing is performed  
- All work aligns with EF01–EF07 and M01–M05 outputs

If any drift is detected, Codex‑LLM MUST halt and escalate to the human operator.

---

## 0. Metadata

- **Milestone ID:** MG06  
- **Milestone Name:** Testing, ETS Integration & Governance  
- **Version:** v1.1  
- **Classification:** Governance Milestone (MG)  
- **Role:** Consolidate and formalize EchoForge’s testing and verification plan.

---

## 1. Status Tracking Model

Every task MUST contain a **Status Block**:

```markdown
- **Status:** pending  <!-- pending | in_progress | blocked | deferred | done -->
- **Last Updated:** —
- **Notes:** —
```

Codex-LLM MUST only edit these three fields when updating status.  
For deeper planning, add an optional **Subtasks** section directly beneath the Description:

```markdown
#### Subtasks
- [ ] ST01 — Short label (link to detailed plan doc)
- [ ] ST02 — …
```

- Use the checklist for governance-visible tracking.  
- Link each line to a supporting plan/ETS document (`pm/milestone_tasks/MG06_Tnn_Subtask_Plan.md`, etc.) where detailed research, test matrices, and notes live.  
- Keep the milestone file concise; put expanded rationale, research, and test plans in the linked document.


---

## 2. References

Same as v1.0 (previous M06), unchanged — this milestone reclassifies, not redefines.

---

## 3. Tasks

(Full tasks preserved from M06 v1.0. No functional change, only milestone-classification change.)

---

## 4. Exit Criteria

Same as M06 v1.0, with this additional requirement:

### **MG06‑X:**  
Codex‑LLM MUST produce a Drift Report summarizing whether any inconsistencies or specification ambiguities were detected across M01–M06.

