# EchoForge Activation Packet — v1.1

## Summary of Changes from v1.0
- Added: `protocols/EP/Codex_LLM_Engagement_Protocol_v1.0.md`
- Removed: `protocols/AcronRP/AcronRP_v01.md`
- Retained: ArtfGen
- Updated initialization sequence to load Engagement Protocol before MTS & milestones
- Updated governance rules to defer to Engagement Protocol for ambiguity, escalation, drift detection

---

## 1. Repository Layout (Contract)

```text
pm/
  milestones/
  status_logs/
  decisions/

protocols/
  MxVA/
  MTS/
  ETS/
  ESJ/
  ArtfGen/
  EP/
    Codex_LLM_Engagement_Protocol_v1.0.md

project-scope/
  strategic/
  tactical/
```

---

## 2. Strategic vs Tactical Context

### Strategic (`project-scope/strategic/`)
High-altitude architecture, purpose, boundaries, components.

### Tactical (`project-scope/tactical/`)
Domain specs, APIs, pipelines, infrastructure.

Codex loads **strategic first**, then **tactical**.

---

## 3. Protocols & Governance

### MxVA
Defines architectural workflow.

### MTS
Defines milestone/task integrity.

### ETS
Defines test-first discipline.

### ESJ
Defines justification depth.

### ArtfGen
Defines artifact creation rules.

### Codex Engagement Protocol (**new in v1.1**)
Defines:
- Codex operating mode
- Ambiguity handling
- Escalation rules
- Drift detection
- CIP suppression
- Behavioral boundaries

Codex MUST load this early.

---

## 4. Milestones

Codex MUST:
- Load M01 → M04  
- Only mutate Status Blocks  
- Not modify task scope unless instructed

---

## 5. Codex Initialization Sequence (Updated)

### Step 0 — Load Engagement Protocol
`protocols/EP/Codex_LLM_Engagement_Protocol_v1.0.md`

### Step 1 — Load Core Protocols
MxVA, MTS, ArtfGen, ESJ, ETS

### Step 2 — Load Strategic
Project overview, architecture, components, boundaries

### Step 3 — Load Tactical
EF01, EF05, EF06, EF07, INF-series

### Step 4 — Load Milestones
M01–M04

---

## 6. Drift & Safety Rules

- Specs override code
- Missing info → ask human
- Do not self-infer critical behavior
- Modify Status Blocks only
- Follow Engagement Protocol for all operational decisions

---

## 7. Human–AI Contract

Codex:
- Operates only within given specifications
- Requests clarification on ambiguity
- Follows Engagement Protocol + MTS

Human:
- Provides missing artifacts when referenced
- Approves architectural changes
- Guides milestone progression

---

## 8. Version History
- **v1.1** — Added Codex Engagement Protocol; removed AcronRP; updated initialization
- **v1.0** — Initial Activation Packet

