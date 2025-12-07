"""Database connection helpers."""

from sqlalchemy import create_engine

from ...config import load_settings

settings = load_settings()

ENGINE = create_engine(settings.database_url, echo=False, future=True)
