# Decision: Use INF-01 YAML Profiles as Whisper Configuration Source (2025-12-07)

## Context
- Milestone: M02 — Processing Pipeline (task M02-T02a)
- Prompt: While wiring the Whisper-powered INF-04 gateway, we noticed that the client was still reading raw `.env` values even though the rest of the application consumes the INF-01 config profiles.
- Requirement: Keep the desktop stack OS-agnostic (Windows/macOS/Linux) and aligned with existing configuration governance.

## Decision
1. Treat the `config/profiles/*.yaml` entries (specifically `llm.whisper`) as the canonical source of truth for all Whisper toggles, model choices, and decode options.
2. Retain `.env` variables only as optional overrides for development or emergency tuning; they cannot introduce new keys that are absent from the profile schema.
3. Load Whisper settings exclusively through `backend.app.config.load_settings()` so every runtime component (workers, API, desktop host, tests) observes identical values regardless of operating system.

## Rationale
- Ensures configuration parity with other INF services (database, capture, job queue) and prevents drift between shells/platforms.
- INF-01 profile files already travel with packaged builds, which keeps Whisper usable in offline or installer-driven scenarios without depending on environment managers.
- Restricting `.env` to overrides keeps local developer ergonomics while avoiding accidental divergence in production deployments.

## Follow-Ups
1. Finish updating the config loader and Whisper client to read from `settings.llm.whisper`, falling back to `.env` only when explicitly set.
2. Refresh `.env.example`, README, and any ops docs to clarify the override-only behavior.
3. Add regression tests covering both default YAML values and override scenarios so the contract stays stable across OS targets.
