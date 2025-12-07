# Decision: EF/INF Test Tagging Strategy (2025-12-07)

## Context
- Milestone linkage: MG06 (Testing Discipline) and M02/M03 regression safety needs when iterating on EF/INF services.
- User request (2025-12-07): "Prototype this now please and lets include tooling support" — referring to selective execution of EF/INF-related unit tests.
- Copilot recommendation/response: introduce explicit pytest markers plus coverage annotations so contributors can target EF-02/EF-06 and INF-02/INF-04 suites without running the entire test graph.

## Options Considered
1. **Pytest markers defined in `pytest.ini`** (adopted): codify `ef02`, `ef06`, `inf02`, `inf04` markers and apply them via `pytestmark` blocks inside each concerned test module.
2. **Directory-based filtering only**: rely on filesystem layout (e.g., `tests/ef02/...`) and manual invocation patterns instead of formal markers.
3. **Ad-hoc documentation**: keep an internal wiki/table describing which files cover which specs, but no automated filtering.

## Decision
Adopt pytest marker-based tagging, starting with `pytest.ini` marker definitions and module-level `pytestmark` assignments (prototype committed in `tests/unit/test_transcription_worker.py`). Treat marker coverage as the canonical way to select EF/INF suites during refactors, CI slices, or milestone verification runs.

## Rationale
- **Tooling-backed filtering:** `pytest -m ef02` now runs only EF-02-tagged tests, aligning with the original request for "tooling support" beyond documentation.
- **Spec traceability:** Marker names mirror EF/INF identifiers, making it obvious which specs a test asserts and easing compliance reviews.
- **Low lift / high leverage:** Requires only lightweight config plus comments, yet immediately benefits local dev loops and CI targeting.
- **Scalable pattern:** Additional specs (e.g., EF05, INF03) can piggyback on the same approach without reorganizing folders.

## Cons Acknowledged
- Requires maintainers to keep marker lists in sync with actual coverage; drift could give false confidence.
- Marker proliferation may clutter modules if overused, so discipline is needed to tag only meaningful scope.
- Selective runs can hide cross-cutting regressions if developers rely exclusively on narrow markers.

## Follow-Ups
1. Extend marker annotations to the remaining EF/INF-facing test modules referenced in milestones M01–M05.
2. Add a short how-to snippet in `tests/README.md` describing marker usage and sample commands (`pytest -m ef06`).
3. Consider CI matrix entries (or Make/Invoke targets) that exercise marker-filtered suites to keep the workflow discoverable.

## Notes for Reviewers
- This decision logs both the user request and the implemented recommendation so future contributors understand why pytest markers appeared.
- Revisit the strategy only if a more expressive test selection mechanism (e.g., `tox` envs or tagging via `nox`) materially improves ergonomics over the current marker pattern.
