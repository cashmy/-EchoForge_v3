# Decision: Capture Config Profiles & Watch Roots (2025-12-07)

## Context
- Milestone: M01 — Capture & Ingress (tasks M01-T03/M01-T05/M01-T08/M01-T09).
- Specs referenced: `INF01_ConfigService_Spec_v1.0.md`, `EF01_CaptureService_Interfaces_Spec_v1.1.md`, `EchoForge_Runtime_Shapes_Spec_v1.0.md`.
- Implementation currently assumes Config Service provides per-runtime watch root definitions, queue endpoints, and manual capture hashing toggles even though the concrete profile documents are not yet published.

## Options Considered
1. **Hard-code watch roots and hashing behavior in EF-01** — fastest to implement but violates INF-01 contract and complicates runtime-shape portability.
2. **Delay watcher/manual capture wiring until Config profiles exist** — stalls M01 exit criteria.
3. **Document interim assumptions now and require Config profiles to honor them** — allows progress while signaling governance debt.

## Decision
Adopt option 3: codify the interim configuration assumptions and require future Config Service profiles (`dev`, `desktop`) to expose:
- `capture.watch_roots` — array of objects with `root_path`, `channel`, and `runtime_shape` hints so EF-01 can scaffold directories per runtime.
- `capture.job_queue_profile` — mapping to INF-02 endpoints/credentials for the local desktop/dev runtimes.
- `capture.manual_text.hashing` — enum describing the fingerprint recipe for manual text so ETS can assert consistent behavior between CLI/API and watcher flows.

EF-01 may continue reading these values from the provisional config loader, but the assumptions must be validated once INF-01 publishes the official profiles.

## Rationale
- Maintains alignment with INF-01 by treating configuration as data, not code, even though profile files are pending.
- Keeps watcher + `/api/capture` feature work unblocked for ShapeA/ShapeB while documenting the requirement for final Config assets.
- Makes it explicit that multiple runtime shapes may point to different watch roots or queue targets, informing packaging work in later milestones.

## Follow-Ups
1. Update the Config loader schema (and associated docs) to reflect the `capture.*` keys listed above.
2. Coordinate with INF-01 owners to publish actual `dev` and `desktop` profile files before MG milestones.
3. Add ETS coverage (once config fixtures exist) that loads these profiles and verifies EF-01 scaffolds/watchers accordingly.
4. Reference this decision from future desktop packaging tasks so installers know which directories and config keys to provision.

## Notes for Reviewers
- This decision does **not** add new behavior; it documents the assumptions already embedded in EF-01 code so governance can track them.
- If Config Service later introduces a richer schema (per-user overrides, secrets), update this decision or supersede it with a new entry.
