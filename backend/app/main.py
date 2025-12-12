"""FastAPI entrypoint for EchoForge backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routers import capture, dashboard, entries, health, taxonomy
from .config import load_settings
from .domain.ef01_capture.watch_folders import ensure_watch_roots_layout


def create_app() -> FastAPI:
    """Instantiate the FastAPI app and register routers."""

    settings = load_settings()
    ensure_watch_roots_layout(settings.watch_roots)
    application = FastAPI(title="EchoForge API", version="0.1.0")
    allowed_origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    }
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (
        health.router,
        entries.router,
        dashboard.router,
        capture.router,
        taxonomy.router,
    ):
        application.include_router(router)
    return application


app = create_app()
