# MG07 — Deployment, Packaging & Runtime Integration — v1.1  
## (Governance Milestone — Not a Build Milestone)

---

## ⚠ Purpose Clarification (Critical)

This milestone is a **Governance Milestone**, not part of implementation.

All functional components, pipelines, schemas, migrations, UI structures, and APIs MUST  
already exist and pass MG06 governance checks *before MG07 begins*.

MG07 focuses exclusively on:

- Packaging  
- Runtime integration  
- Deployment correctness  
- Cross‑platform distribution  
- Drift detection during runtime shaping  

No feature‑development tasks are allowed here.

---

## 🔍 Drift Check

Codex‑LLM MUST validate:

- No schema invention occurs in MG07  
- No migration logic is rewritten here  
- No new API endpoints are introduced  
- No pipeline logic is modified  
- No milestone reordering is attempted  

If drift is detected, halt and escalate.

---

## 0. Metadata

- **Milestone ID:** MG07  
- **Milestone Name:** Deployment, Packaging & Runtime Governance  
- **Version:** v1.1  
- **Classification:** Governance Milestone (MG)

---

## 1. Status Tracking Model

Only modify:

```
Status
Last Updated
Notes
```

---

## 2. References

Same as M07 v1.0; unchanged in content.

---

## 3. Tasks

(Tasks identical to M07 v1.0; reclassified not redesigned.)

Includes:

- Packaging strategy  
- Runtime config strategy  
- Deployment DB strategy (NOT schema design; packaging only)  
- Electron packaging  
- Post‑build smoke tests  
- Release process governance  

---

## 4. Exit Criteria

Same as M07 v1.0, with the additional governance requirement:

### **MG07‑X:**  
Codex‑LLM MUST verify runtime packaging introduces **no architectural drift**  
and matches EF07 + runtime shapes exactly.

