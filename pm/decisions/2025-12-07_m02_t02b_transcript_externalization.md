# Decision: Add M02-T02b for Transcript Externalization (2025-12-07)

## Context
- Milestone: M02 — Processing Pipeline.
- Related specs: `EF06_EntryStore_Spec_v1.1.md` (verbatim_path guidance), `EF06_EntryStore_Addendum_v1.2.md`, `INF01_ConfigService_Spec_v1.0.md`, `EF07_EchoForgeApiAndUi_Spec_v1.1.md`.
- Gap observed while closing M02-T02a: EF-02 worker writes transcripts into EF-06 fields but never externalizes them to disk, despite EF-06 expecting `verbatim_path` references. Handling was implied but not implemented.

## Options Considered
1. **Defer transcript files to later milestone** — leave EF-02 storing only text blobs in EF-06 for now.
2. **Implement ad-hoc transcript saving during M02-T02a** — tack the work onto the Whisper integration task without clear config/docs.
3. **Create a dedicated subtask (M02-T02b)** — scope, document, and execute transcript externalization with proper config, worker changes, and ETS coverage.

## Decision
Create **M02-T02b — Externalize EF-02 Transcripts to Filesystem** with the following scope:
- Introduce profile-level config (`llm.whisper.transcript_output_root` and optional public URL base) to dictate where transcripts are written.
- Update watcher/bootstrap code to ensure the directory exists and is permissioned when Whisper support is enabled.
- Modify `transcription_worker` so each successful job writes the transcript (and optional segments JSON) to the configured root, records the file path + preview snippet in EF-06 (`verbatim_path`, `verbatim_preview`, `content_lang`), and ties retention to entry lifecycle.
- Extend unit tests + ETS guidance to prove transcripts land on disk and the resulting EF-06 records link to them.
- Refresh EF-06/INF-01 specs and governance artifacts to explicitly describe the behavior.

## Rationale
- Keeps the Whisper integration task focused while ensuring the EF-06 spec requirement (externalized verbatim content) is fulfilled.
- Provides a single, reproducible configuration path instead of scattering ad-hoc `.env` overrides.
- Enables the upcoming EF-03/EF-04/EF-07 milestones to rely on persisted transcript files (e.g., UI download links, normalization pipelines) without rework.

## Follow-Ups
1. Implement the new config keys and documentation per decision `2025-12-07_transcript_output_root_profiles_only.md`.
2. Execute the code changes + tests under the new M02-T02b task before closing it out.
3. Update milestone tracker and status logs when work is in progress/done.
