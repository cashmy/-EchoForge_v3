# EchoForge v3 — AI Coding Instructions

You are an AI coding agent working inside the **EchoForge v3** repository. This project implements an Electron-hosted desktop app with a local API, Postgres-backed EntryStore, and a milestone-driven architecture.

## Big-Picture Architecture

- Strategic architecture docs live in: `project-scope/strategic/`
  - Start with: `EchoForge_Architecture_Overview_v1.1.md`
  - Also see: `EchoForge_Component_Summary_v1.1.md`
- Tactical specs live in: `project-scope/tactical/`
  - `EF0x_*.md` → domain & UI/API specs (e.g., EF06 EntryStore, EF07 API/UI)
  - `INF0x_*.md` → infrastructure services (Config, Job Queue, Logging, LLM Gateway)
- Postgres is the primary DB. Schema and behavior are defined in:
  - `EF06_EntryStore_Spec_v1.1.md` (+ any addendums)

## Milestones & Governance

- Project planning and execution live in: `pm/`
  - `pm/milestones/` → milestone task lists (M01–M05, MG06–MG07)
  - `pm/Activation_Packet_v*.md` → how to use milestones with an AI agent
- Governance rules for milestone execution live in:
  - `pm/MG00_Milestone_Execution_Rules_v1.1.md`
- When doing **milestone-guided work**, read:
  - `MG00_Milestone_Execution_Rules_v1.1.md`
  - Relevant `M0x_*` or `MG0x_*` task file
    Then align your changes to the tasks and exit criteria in those files.

## How to Be Productive Quickly

- Before modifying **core domain or schema**:
  - Read: `EF06_EntryStore_Spec_v1.1.md` (and any addendum)
- Before modifying **API or UI behavior**:
  - Read: `EF07_EchoForgeApiAndUi_Spec_v1.1.md`
  - Read: `EF07_Api_Contract_v1.2.md`
  - For Electron/host wiring: `EF07_DesktopHostAdapter_Spec_v0.1.md`
- Before changing **infrastructure behavior**:
  - Config: `INF01_ConfigService_Spec_v1.0.md`
  - Jobs: `INF02_JobQueueService_Spec_v1.0.md`
  - Logging: `INF03_LoggingService_Spec_v1.0.md`
  - LLM Gateway: `INF04_LlmGateway_Spec_v1.0.md`

## Conventions & Patterns

- Treat the **spec files as the source of truth**:
  - Implement or refactor code to match specs rather than inventing new behavior.
  - If specs and code disagree, prefer specs and note the discrepancy in `pm/status_logs/` or milestone notes.
- Follow the **milestone structure** when doing larger changes:
  - M01–M05 are build milestones (features, pipeline, UI).
  - MG06–MG07 are governance milestones (testing, packaging, runtime).
- Avoid silently introducing:
  - New DB tables or fields not mentioned in EF06/related specs.
  - New API endpoints not mentioned in EF07 specs.
  - Cross-cutting behavior that bypasses INF services (Config, Logging, LLM Gateway).

## When Unsure

- If a change touches multiple components (DB + API + UI), skim:
  - `EchoForge_Architecture_Overview_v1.1.md`
  - The relevant milestone file under `pm/milestones/`.
- If architecture or intent is unclear:
  - Propose 2–3 options with tradeoffs.
  - Point to the spec lines or milestone tasks you’re interpreting.
