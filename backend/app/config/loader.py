"""INF-01 Config loader placeholder."""

from pydantic import BaseSettings


class Settings(BaseSettings):
    environment: str = "dev"


def load_settings() -> Settings:
    return Settings()
