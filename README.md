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
