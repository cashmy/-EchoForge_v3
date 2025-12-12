"""Shared API dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Request

from ..domain.ef01_capture.runtime import InfraJobQueueAdapter
from ..domain.ef06_entrystore.gateway import (
    EntryStoreGateway,
    build_entry_store_gateway,
)
from ..domain.taxonomy import PostgresTaxonomyRepository, TaxonomyService

__all__ = [
    "get_entry_gateway",
    "get_job_enqueuer",
    "get_taxonomy_service",
    "ActorContext",
    "get_actor_context",
]

ACTOR_ID_HEADER = "x-actor-id"
ACTOR_SOURCE_HEADER = "x-actor-source"
DEFAULT_ACTOR_ID = os.getenv("DEFAULT_ACTOR_ID", "api_request")
DEFAULT_ACTOR_SOURCE = os.getenv("DEFAULT_ACTOR_SOURCE", "ef07_api")


@dataclass(frozen=True)
class ActorContext:
    """Represents the operator initiating an API call."""

    actor_id: str
    actor_source: str


@lru_cache()
def _entry_gateway_singleton() -> EntryStoreGateway:
    return build_entry_store_gateway()


def get_entry_gateway() -> EntryStoreGateway:
    """Return the process-wide EntryStore gateway instance."""

    return _entry_gateway_singleton()


def get_job_enqueuer() -> InfraJobQueueAdapter:
    """Return a job queue adapter for enqueueing ingestion work."""

    return InfraJobQueueAdapter()


def get_actor_context(request: Request) -> ActorContext:
    """Extract actor metadata from request headers (defaults when missing)."""

    actor_id = (request.headers.get(ACTOR_ID_HEADER) or "").strip() or DEFAULT_ACTOR_ID
    actor_source = (
        request.headers.get(ACTOR_SOURCE_HEADER) or ""
    ).strip() or DEFAULT_ACTOR_SOURCE
    return ActorContext(actor_id=actor_id, actor_source=actor_source)


@lru_cache()
def _taxonomy_service_singleton() -> TaxonomyService:
    env_value = os.getenv("ALLOW_TAXONOMY_DELETE")
    if env_value is None:
        allow_delete = True
    else:
        allow_delete = env_value.lower() in {"1", "true", "yes"}
    repository = PostgresTaxonomyRepository()
    return TaxonomyService(
        allow_hard_delete=allow_delete,
        repository=repository,
    )


def get_taxonomy_service() -> TaxonomyService:
    """Return the taxonomy service singleton."""

    return _taxonomy_service_singleton()
