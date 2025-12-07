"""Shared API dependencies."""

from __future__ import annotations

from functools import lru_cache

from ..domain.ef01_capture.runtime import InfraJobQueueAdapter
from ..domain.ef06_entrystore.gateway import (
    EntryStoreGateway,
    InMemoryEntryStoreGateway,
)

__all__ = ["get_entry_gateway", "get_job_enqueuer"]


@lru_cache()
def _entry_gateway_singleton() -> EntryStoreGateway:
    return InMemoryEntryStoreGateway()


def get_entry_gateway() -> EntryStoreGateway:
    """Return the process-wide EntryStore gateway instance."""

    return _entry_gateway_singleton()


def get_job_enqueuer() -> InfraJobQueueAdapter:
    """Return a job queue adapter for enqueueing ingestion work."""

    return InfraJobQueueAdapter()
