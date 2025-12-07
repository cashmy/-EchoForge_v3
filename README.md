# EchoForge v3 Scaffold

This repository contains the EchoForge v3 desktop experience, composed of:

- `backend/`: FastAPI service with EntryStore adapters, INF integrations, and Alembic migrations.
- `frontend/`: React + Vite console that connects to the local API and will be embedded by the desktop host.
- `desktop-host/`: Electron shell that loads the frontend and proxies to local services per EF07 specs.
- `packages/shared/`: DTOs and registries shared across services.
- `scripts/`: Developer helpers (dev servers, seed scripts, ETS runner).
- `docker/`: Compose files for Postgres and supporting infra.
- `tests/`: End-to-end and desktop smoke harnesses.

Use the per-folder READMEs for focused workflows. Consult `pm/milestone_tasks/` for milestone-aligned tasks before extending the scaffold.

## Whisper Configuration

The INF-04 transcription gateway ships disabled by default. Copy `.env.example` to `.env` and set `ECHOFORGE_WHISPER_ENABLED=1` when you want the backend to load the local faster-whisper model instead of the stub. All tuneable knobs (model id, device/compute type, decoding hyper-parameters, and VAD settings) are exposed as `ECHOFORGE_WHISPER_*` variables in `.env.example`; adjust them per deployment requirements. Leave the block untouched (or set `ENABLED=0`) when the target environment does not have GPU resources so the gateway will continue to short-circuit safely.
