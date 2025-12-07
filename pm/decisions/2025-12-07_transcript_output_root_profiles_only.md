# Decision: Transcript Output Root Lives in Config Profiles (2025-12-07)

## Context
- Milestone: M02 — Processing Pipeline (EF-02 transcription feeding EF-06 verbatim storage).
- Specs referenced: `EF06_EntryStore_Spec_v1.1.md` (verbatim_path guidance), `INF01_ConfigService_Spec_v1.0.md` (profile loader), `EF07_EchoForgeApiAndUi_Spec_v1.1.md` (future UI surfacing of transcripts).
- EF-02 worker needs a deterministic filesystem location to emit full transcript files so `entries.verbatim_path` can reference them. Earlier discussion proposed adding both YAML profile settings and optional `.env` overrides for flexibility.

## Options Considered
1. **Profile-only configuration** — define the transcript output root (and optional public URL base) exclusively inside `config/profiles/*.yaml`.
2. **Profile + `.env` overrides** — keep the profile default but allow `ECHOFORGE_TRANSCRIPT_OUTPUT_ROOT` or similar env vars to override per machine.

## Decision
Adopt **profile-only configuration** for transcript output roots. Each INF-01 profile will define the location (e.g., `llm.whisper.transcript_output_root`) and, if needed, a public URL base. No `.env` override will be supported for this setting.

## Rationale
- Transcript storage paths change rarely; keeping them in profiles avoids extra configuration surface that every developer/operator must understand.
- Watcher + transcription workers are intended to run continuously in the background; a single source of truth prevents drift between services started under different shells/envs.
- Simplifies open-source onboarding: contributors adjust the YAML once instead of learning yet another env var, and CI/CD environments can rely on committed profile defaults.
- Keeps INF-01 behavior consistent with other long-lived filesystem settings (watch roots, job queue endpoints) that already live solely in profiles.

## Follow-Ups
1. Extend INF-01 loader to parse `transcript_output_root` (and optional `transcript_public_base_url`) from each profile under the `llm.whisper` section, defaulting to a repo-relative path for `dev`.
2. Update documentation (`config/README`, `tests/README`, EF-06 spec addendum) to reference the new profile keys and the expectation that transcripts are externalized files.
3. Modify `transcription_worker.handle` to read the setting from INF-01, write transcript files to that root, and populate `verbatim_path`/`verbatim_preview` on EF-06 entries.
4. Add ETS/unit coverage ensuring the configured path is honored and that relocating the profile value moves the output files accordingly.
