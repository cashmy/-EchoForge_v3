"""Database connection helpers."""

from sqlalchemy import create_engine

ENGINE = create_engine(
    "postgresql+psycopg://user:pass@localhost:5432/echoforge", echo=False
)
