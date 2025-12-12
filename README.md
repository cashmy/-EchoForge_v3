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

## Technology Stack Overview

**Backend**
- Python 3.11 runtime with FastAPI + Uvicorn for the HTTP interface
- SQLAlchemy ORM backed by PostgreSQL 15, with Alembic managing schema migrations
- Pydantic models + shared DTOs for EF-06 EntryStore and EF-05 semantic integrations
- INF-02 job dispatch layer (Celery + Redis) for asynchronous summarization/classification work

**Frontend**
- React 18 SPA built with Vite per M05 guidance
- Tailwind CSS utility system + CSS custom properties for theming (light/dark/system)
- React Router 7 for nested dashboard / entries / settings flows
- React Query + Zustand for server-state caching and thin global UI flags
- Headless UI / Radix primitives with selective MUI DataGrid usage for heavy table UX

**Middleware / Host Services (optional)**
- Electron Desktop Host Adapter (Shape B) to launch backend processes and expose guarded `platform.*` IPC methods
- INF-01 Config Service for runtime settings + feature toggles
- INF-04 LLM Gateway for Whisper + GPT workloads, keeping EF-07 UI host-agnostic
- INF-03 Logging Service for unified event capture across backend + UI

## Whisper Configuration

The INF-04 transcription gateway ships disabled by default. Copy `.env.example` to `.env` and set `ECHOFORGE_WHISPER_ENABLED=1` when you want the backend to load the local faster-whisper model instead of the stub. All tuneable knobs (model id, device/compute type, decoding hyper-parameters, and VAD settings) are exposed as `ECHOFORGE_WHISPER_*` variables in `.env.example`; adjust them per deployment requirements. Leave the block untouched (or set `ENABLED=0`) when the target environment does not have GPU resources so the gateway will continue to short-circuit safely.
