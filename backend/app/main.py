"""FastAPI entrypoint for EchoForge backend."""

from fastapi import FastAPI

from .api.routers import capture, entries, health, taxonomy
from .config import load_settings
from .domain.ef01_capture.watch_folders import ensure_watch_roots_layout


def create_app() -> FastAPI:
    """Instantiate the FastAPI app and register routers."""

    settings = load_settings()
    ensure_watch_roots_layout(settings.watch_roots)
    application = FastAPI(title="EchoForge API", version="0.1.0")
    for router in (health.router, entries.router, capture.router, taxonomy.router):
        application.include_router(router)
    return application


app = create_app()
