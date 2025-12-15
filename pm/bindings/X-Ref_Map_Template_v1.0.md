# X-Ref Map Template v1.0
Quick cross-reference between Milestones (Mnn/MGnn/MInn) and Architecture Slices (EFnn + UI + SPG + ETS).

---

## 1) Legend

### Link Weight
- **P** = Primary (this milestone *depends on* this artifact to deliver)
- **S** = Secondary (touched/impacted but not the delivery driver)
- **D** = Deferred (explicitly out-of-scope or postponed)
- **F** = Frozen (intentionally unchanged during this milestone)
- **—** = No relationship / not relevant

### Surface Tags (optional)
- **U** = User Surface
- **A** = Artifact Surface
- **I** = Internal Processing Surface
- **E** = Ephemeral

Example: `P(U)` or `S(A)`.

---

## 2) Master Index

### 2.1 Milestones
| ID   | Name | Type | Status | Cutline (1-line) | Owner |
| ---- | ---- | ---- | ------ | ---------------- | ----- |
| M01  |      | M    |        |                  |       |
| MG01 |      | MG   |        |                  |       |
| MI99 |      | MI   |        |                  |       |

### 2.2 Architecture / Specs
| ID    | Artifact                         | Category   | Status | Primary Surface | Notes |
| ----- | -------------------------------- | ---------- | ------ | --------------- | ----- |
| EF01  |                                  | Tactical   |        |                 |       |
| EF07  |                                  | Tactical   |        |                 |       |
| SPG   | Surface & Persistence Governance | Governance |        |                 |       |
| ETS   | Enac Testing Subsystem           | Governance |        |                 |       |
| UI-WF | Wireframes                       | UI/UX      |        | U               |       |

---

## 3) Cross-Reference Matrix (Milestones × Artifacts)

> Keep this table *thin* and high-signal.  
> Use P/S/D/F markers. If needed, add surface tags.

| Milestone ↓ \\ Artifact → | EF01 | EF02 | EF03 | EF04 | EF05 | EF06 | EF07 | UI-WF | SPG | ETS |
| ------------------------- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ----- | --- | --- |
| M01                       |      |      |      |      |      |      |      |       |     |     |
| M02                       |      |      |      |      |      |      |      |       |     |     |
| M03                       |      |      |      |      |      |      |      |       |     |     |
| M04                       |      |      |      |      |      |      |      |       |     |     |
| MG01                      |      |      |      |      |      |      |      |       |     |     |
| MI99                      |      |      |      |      |      |      |      |       |     |     |

---

## 4) Per-Milestone “Binding Block” (Fast Read)

> Use this for each active milestone. This is the “truth stamp” that prevents drift.

### 4.1 Milestone: M__ — <Name>
**Outcome:** <one sentence user/value outcome>

**Primary Artifacts (P):**
- EF__ — <why it’s primary>
- UI-WF — <why it’s primary>

**Secondary Artifacts (S):**
- EF__ — <what’s impacted>

**Deferred / Forbidden (D):**
- EF__ — <why deferred>
- <Behavior/Flow> — <explicitly out-of-scope>

**Frozen (F):**
- EF__ — <must not change>

**SPG Notes (if relevant):**
- Surfaces: <U/A/I/E>
- Persistence bias: artifact_first | entry_first
- Forbidden mutations: <e.g., no PATCH in entry lifecycle>

---

## 5) Per-Artifact “Justification Block” (Optional)

> Useful for EFnn docs that tend to attract scope creep.

### 5.1 Artifact: EF__ — <Name>
**Primary Milestones (P):**
- M__ — <why>

**Secondary Milestones (S):**
- M__ — <impact>

**Cutline Notes:**
- Not permitted during: <M__ / release train>
- Surface constraints: <U/A/I/E>
- Persistence rule: <e.g., ledger only, no new entry columns>

---

## 6) Optional Mermaid View (High-Level)

> Keep it small. Only show P links + major S links for active milestones.

```mermaid
flowchart LR
  subgraph Milestones
    M01["M01"]:::m
    M03["M03"]:::m
    M04["M04"]:::m
  end

  subgraph Artifacts
    EF06["EF06"]:::a
    EF07["EF07"]:::a
    EF04["EF04"]:::a
    UIWF["UI-WF"]:::u
    SPG["SPG"]:::g
  end

  M03 -->|P| EF06
  M03 -->|P| EF07
  M03 -.->|S| SPG
  M04 -->|P| UIWF
  M04 -.->|D| EF04

  classDef m stroke-width:2px;
  classDef a stroke-dasharray: 2 2;
  classDef u stroke-dasharray: 4 2;
  classDef g stroke-dasharray: 6 2;
