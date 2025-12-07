"""FastAPI entrypoint for EchoForge backend."""

from fastapi import FastAPI

from .api.routers import capture, entries, health, taxonomy


def create_app() -> FastAPI:
    """Instantiate the FastAPI app and register routers."""

    application = FastAPI(title="EchoForge API", version="0.1.0")
    for router in (health.router, entries.router, capture.router, taxonomy.router):
        application.include_router(router)
    return application


app = create_app()
