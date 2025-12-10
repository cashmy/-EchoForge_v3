# M05 — UI Framework, Layout & Interaction — v1.0

---

## 0. Metadata

- **Milestone ID:** M05  
- **Milestone Name:** UI Framework, Layout & Interaction  
- **Version:** v1.0  
- **Scope Summary:**  
  Define and implement the initial user interface structure for EchoForge v3, including:
  - Core layout and navigation for the Electron-hosted SPA
  - Tailwind + (optional) MUI integration strategy
  - Theming (light/dark/custom)
  - Dashboard, search, and entry-detail surfaces wired to EF-07 APIs
  - Basic interaction patterns (lists, filters, detail panels, forms)
  - Alignment with runtime shapes and EF-07 responsibilities

M05 focuses on **user-facing structure and behavior**, not pixel-perfect visual design.

- **Primary Components:**  
  - EF07_EchoForgeApiAndUi_Spec_v1.1.md  
  - EF07_Api_Contract_v1.2.md  
  - EF07_DesktopHostAdapter_Spec_v0.1.md  
  - M04_Dashboard_Search_Aggregation_Tasks_v1.0.md  
- **Governance:**  
  - Milestone_Task_Subsystem_v1.1.md  
  - EnaC_TestingSubsystem_v1.0.md  
  - MxVA_MachineSpec_v1.0.md  

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
- Link each line to a supporting plan/ETS document (`pm/milestone_tasks/M05_Tnn_Subtask_Plan.md`, etc.) where detailed research, test matrices, and notes live.  
- Keep the milestone file concise; put expanded rationale, research, and test plans in the linked document.

--
## 2. References

- `project-scope/strategic/EchoForge_Architecture_Overview_v1.1.md`  
- `project-scope/strategic/EchoForge_Component_Summary_v1.1.md`  
- `project-scope/tactical/EF07_EchoForgeApiAndUi_Spec_v1.1.md`  
- `project-scope/tactical/EF07_Api_Contract_v1.2.md`  
- `project-scope/tactical/EF07_DesktopHostAdapter_Spec_v0.1.md`  
- `pm/milestones/M04_Dashboard_Search_Aggregation_Tasks_v1.0.md`  

---

## 3. Tasks

---

### M05-T01 — Confirm UI Runtime Shape & Shell Boundaries

- **Type:** design  
- **Depends On:** EF07_DesktopHostAdapter_Spec_v0.1.md, EF07_EchoForgeApiAndUi_Spec_v1.1.md  
- **ETS Profiles:** ETS-Arch  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Document a concise confirmation note that:

- Shape B (Electron desktop) is the primary runtime for v1.  
- The SPA runs inside the desktop host using a local web server or bundled assets.  
- The boundary between host (Electron) and app (SPA) is clearly defined:
  - Which responsibilities remain in Electron (windowing, menus, OS integration).  
  - Which responsibilities live entirely in the SPA (routing, state, UI flows).  

Output:  
- A short design addendum or comment in `EF07_DesktopHostAdapter_Spec_v0.1.md` or a new `EF07_DesktopHostAdapter_Addendum_v0.1.md`.

---

### M05-T02 — Choose UI Framework Stack & State Management Approach

- **Type:** design  
- **Depends On:** M05-T01  
- **ETS Profiles:** ETS-Arch, ETS-UX  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Make an explicit decision on:

- Primary UI framework: (e.g., React SPA within Electron).  
- Styling approach: Tailwind as primary, MUI selectively for data-heavy components (tables, forms).  
- State management baseline:
  - Local component state vs lightweight global store (e.g., React Context) vs heavier solution (Redux, Zustand, etc.).  

Document tradeoffs and rationale in a short `UI_Framework_Selection_Note_v1.0.md` under an appropriate folder (e.g., `project-scope/tactical/` or `docs/ui/`).

---

### M05-T03 — Define Global Layout & Navigation Structure

- **Type:** design  
- **Depends On:** M05-T02, M04-T01  
- **ETS Profiles:** ETS-UX  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Design the top-level layout and navigation model, including:

- Core regions:
  - Header/top bar (if any).  
  - Sidebar navigation (domains/types, views).  
  - Main content area (dashboard or list + detail).  
  - Optional secondary panel for detail/insights.  
- Primary navigation flows:
  - Home/Dashboard.  
  - Entries (search/list).  
  - Settings/config (may be stubbed for v1).  

Output:  
- A simple layout diagram or structured description in `UI_Layout_And_Navigation_v1.0.md`.

---

### M05-T04 — Implement Base Layout Shell & Routing

- **Type:** implementation  
- **Depends On:** M05-T03  
- **ETS Profiles:** ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement:

- The root layout component(s) (e.g., `AppShell`, `Sidebar`, `TopBar`).  
- SPA routing structure:
  - `/` → dashboard view.  
  - `/entries` → entries list/search.  
  - `/entries/:id` → entry detail.  
  - `/settings` (optional stub).  

Ensure:

- Layout is responsive enough for typical desktop window sizes.  
- Routing can be driven by Electron deep-links later if needed.

---

### M05-T05 — Implement Theming (Light/Dark + Base Theme Tokens)

- **Type:** implementation  
- **Depends On:** M05-T02  
- **ETS Profiles:** ETS-UX, ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement a minimal theming system:

- Support at least light and dark modes.  
- Define a small set of theme tokens:
  - Background, surface, primary, accent, text, border.  
- Integrate theme switching in a simple, non-intrusive way (menu toggle, settings, or shortcut).  

Tailwind configuration and any MUI theme overrides (if used) should be updated accordingly.

---

### M05-T06 — Wire Dashboard View to `/api/dashboard/summary`

- **Type:** implementation  
- **Depends On:** M04-T04, M05-T04  
- **ETS Profiles:** ETS-API, ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement the Dashboard page:

- Call `GET /api/dashboard/summary`.  
- Render:
  - Pipeline distribution (counts by `ingest_state`).  
  - Top types and domains.  
  - Recent activity or “last N entries” summary if available.  

Keep designs simple and information-dense; visual polish may be deferred.

---

### M05-T07 — Implement Entries List View (Search + Filters)

- **Type:** implementation  
- **Depends On:** M04-T02, M04-T05, M05-T04  
- **ETS Profiles:** ETS-API, ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement the main Entries list view:

- Calls `GET /api/entries` with:
  - Search query (`q`).  
  - Filters (type, domain, ingest_state, source_channel, date range).  
- UI elements:
  - Search box.  
  - Type and Domain dropdowns (using taxonomy endpoints).  
  - Pipeline status filter (ingest_state).  
  - Basic pagination controls.  

Ensure consistent behavior with the API semantics described in EF07 and M04.

---

### M05-T08 — Implement Entry Detail View

- **Type:** implementation  
- **Depends On:** EF06 specs, M02 pipeline tasks, M05-T07  
- **ETS Profiles:** ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement a detail view for a single Entry:

- Shows:
  - Title and key metadata.  
  - Original content/source snippet.  
  - Semantic summary and classification results.  
  - Type and domain (if assigned).  
  - Pipeline state and timestamps.  

Use read-only views for v1; edits can be deferred to a later milestone unless explicitly brought into scope.

---

### M05-T09 — Implement Basic Error & Loading States

- **Type:** implementation  
- **Depends On:** M05-T06, M05-T07  
- **ETS Profiles:** ETS-UX, ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement:

- Global or per-view loading indicators for API calls.  
- Friendly error states when:
  - Dashboard summary cannot be loaded.  
  - Entries list fails to load.  
  - Entry detail fetch fails.  

Error messaging should be helpful but not overwhelming, and should not expose raw stack traces.

---

### M05-T10 — Electron Host Integration Smoke Test

- **Type:** test  
- **Depends On:** M05-T04, M05-T06, M05-T07  
- **ETS Profiles:** ETS-API, ETS-UX  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Perform a basic end-to-end smoke test in the Electron host:

- Launch the desktop app.  
- Navigate between:
  - Dashboard.  
  - Entries list.  
  - Entry detail.  
- Confirm:
  - Layout behaves correctly.  
  - API calls resolve successfully against the configured backend.  
  - No obvious routing or rendering issues.

Document the results in `pm/status_logs/` as a short log entry.

---

### M05-T11 — Define ETS Cases for UI Behavior

- **Type:** test design  
- **Depends On:** M05-T06, M05-T07, M05-T08  
- **ETS Profiles:** ETS-UI, ETS-UX  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define ETS test cases covering:

- Dashboard accurately reflecting `/api/dashboard/summary` data.  
- Search and filters in the Entries list:
  - Correct API parameters.  
  - Correct rendering of results.  
- Detail view showing correct fields and gracefully handling missing optional data.  
- Basic acceptance criteria for theming (e.g., legible text in light/dark modes).

---

### M05-T12 — Capture UI Design Decisions

- **Type:** governance  
- **Depends On:** M05-T02 through M05-T08  
- **ETS Profiles:** —  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Record in `pm/decisions/`:

- Final choice of UI framework and state management.  
- The role of Tailwind vs MUI in this project.  
- The scope and intent of v1 UI:
  - “Functional insight tool” vs “fully polished product.”  
- Any explicit deferrals (e.g., Saved Views, advanced dashboards, entry editing).

---

### M05-T13 — Surface Whisper & Transcript Settings

- **Type:** implementation  
- **Depends On:** M05-T03, M05-T04, MI99-T06  
- **ETS Profiles:** ETS-UX, ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Mirrors MI99-T06; ensure the UI milestone delivers this configuration surface.  

**Description:**  
Add a settings panel (or dashboard card) in the EF-07 desktop UI that reads INF-01 Whisper configuration and displays:

- Whisper enablement state, model, device/compute type.
- Transcript output root path and public base URL (if configured).
- Quick validation indicator (e.g., “path reachable” check or link to open folder).

This gives operators immediate visibility into audio pipeline readiness without digging through YAML or logs. Implementation can be lightweight (read-only), but it must live within the core M05 layout so future settings enhancements have a home.

---

## 4. Exit Criteria

M05 is considered complete when:

1. The UI framework stack and state management model are documented and adopted.  
2. Core layout and navigation are implemented and functional in the Electron host.  
3. Theming (light/dark) works across main views.  
4. Dashboard view is wired to `/api/dashboard/summary` and displays meaningful data.  
5. Entries list supports search, filter, and pagination using `/api/entries`.  
6. Entry detail view is implemented and stable.  
7. Error and loading states are handled in a user-friendly way.  
8. Basic Electron smoke tests pass and are logged under `pm/status_logs/`.  
9. ETS test cases for UI behavior are documented.  
10. UI-related decisions are captured under `pm/decisions/`.
