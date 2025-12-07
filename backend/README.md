# EchoForge Backend

FastAPI scaffold covering EF components, INF services, and ETS hooks.
- INF-01 config profiles now live under `config/profiles/` and drive capture/watch behavior.

## Configuration profiles (INF-01 placeholder)

- `backend.app.config.load_settings()` reads YAML profiles from `config/profiles/`.
- `ECHOFORGE_CONFIG_PROFILE` selects which profile to load (defaults to `dev`).
- `ECHOFORGE_CONFIG_DIR` overrides the directory if you keep profiles elsewhere.
- `DATABASE_URL` still overrides the database URL after the profile is loaded.

Example (Windows PowerShell):

```powershell
$env:ECHOFORGE_CONFIG_PROFILE = "desktop"
python -m backend.app.main
```

## Local database configuration

The backend reads `database_url` from INF-01 settings (via environment variables consumed by `backend.app.config`). By default it targets the local Postgres instance at `postgresql+psycopg://postgres:LuckySebeka@localhost:5432/echo_forge`.

Override this by exporting `DATABASE_URL` (or any env var Pydantic maps onto `database_url`) before starting the API, e.g.:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:LuckySebeka@localhost:5432/echo_forge"
python -m backend.app.main
```

Create the database once via `psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE echo_forge;"` and then run migrations to provision EF-06 tables.

## Database migrations (Alembic)

Alembic scripts live under `backend/migrations/`. The environment pulls connection info from the active INF-01 profile, so ensure your `ECHOFORGE_CONFIG_PROFILE` / `DATABASE_URL` variables are set before running:

```powershell
cd backend
$env:ECHOFORGE_CONFIG_PROFILE = "dev"  # or desktop
alembic upgrade head
```

To create new revisions, run `alembic revision -m "<message>"` from the `backend/` directory. The initial migration (`20251207_add_capture_fingerprint_columns`) adds `capture_fingerprint`, `fingerprint_algo`, and `capture_metadata` columns plus supporting indexes for EF-06 idempotency.

## Sample data seeding

After migrations, populate the `entries` table with demo rows via the seed script (uses the same INF-01 profile/`DATABASE_URL` settings):

```powershell
cd D:\@EchoForge_v3
$env:ECHOFORGE_CONFIG_PROFILE = "dev"
$env:DATABASE_URL = "postgresql+psycopg://postgres:LuckySebeka@localhost:5432/echo_forge"
.\.venv\Scripts\python.exe scripts/seed_db.py
```

You should see `Seeded 3 entries into EF-06.` and can verify the rows in `entries` via psql or pgAdmin. Re-running the script is idempotent; it upserts on `entry_id`.
