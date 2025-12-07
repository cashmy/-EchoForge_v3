# Decision: Track INF-04 Whisper Integration as Dedicated Subtask (2025-12-07)

## Context
- Milestone: M02 — Processing Pipeline
- Trigger: EF-02 worker currently uses a stubbed `transcribe_audio` helper, which limits fidelity for ETS coverage and hides micro-design issues (model configuration, latency, real error codes).
- Stakeholder input: User approved carving out a new task; also noted availability of ~107 WAV samples (~6 GB total) for real ingestion tests once the pipeline can process them.

## Decision
Add a new task under M02 (proposed `M02-T02a — Replace INF-04 Transcription Stub with Whisper Integration`) to cover:
1. Selecting/packaging Whisper (local build vs. hosted API) and wiring it through INF-04 (`backend/app/infra/llm_gateway`).
2. Extending configuration so EF-02 can choose profiles/models and propagate auth/secrets.
3. Updating ETS/CI guidance to handle larger media fixtures and long-running transcription tests.
4. Coordinating with infrastructure for GPU/runtime requirements if needed.

## Rationale
- Keeps EF-02 implementation focused while acknowledging the real-model work is sizable.
- Ensures testing plans (including the provided 6 GB corpus) align with actual LLM behavior rather than stubs.
- Surfaces design decisions (chunking, rate limits, error taxonomy) before wider pipeline milestones depend on them.

## Follow-Ups
1. Insert the new task block into `pm/milestone_tasks/M02_Processing_Pipeline_Tasks_v1.0.md` with status `pending` and reference this decision file.
2. Capture infrastructure requirements (hardware, Docker image updates, secrets) in INF-04 spec addenda if Whisper demands them.
3. When ready, coordinate with the user to place sample WAV files into `watch_roots/audio/incoming/` for end-to-end validation.
