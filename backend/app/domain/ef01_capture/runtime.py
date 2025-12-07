"""Runtime helpers for EF-01 watch folder ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .idempotency import EntryFingerprintReader
from .watcher import (
    EntryCreator,
    JobEnqueuer,
    WatcherOrchestrator,
    build_default_watch_profiles,
)
from ..ef06_entrystore.gateway import InMemoryEntryStoreGateway
from ...infra import jobqueue

__all__ = [
    "InfraJobQueueAdapter",
    "run_watch_once",
]


class InfraJobQueueAdapter(JobEnqueuer):
    """Delegates to the INF-02 job queue adapter."""

    def __init__(self, enqueue_fn=jobqueue.enqueue) -> None:
        self._enqueue = enqueue_fn

    def enqueue(self, job_type: str, *, entry_id: str, source_path: str) -> None:  # noqa: D401
        payload = {"entry_id": entry_id, "source_path": source_path}
        self._enqueue(job_type, payload)


def run_watch_once(
    watch_roots: Iterable[str | Path],
    *,
    entry_gateway: EntryCreator | None = None,
    fingerprint_reader: EntryFingerprintReader | None = None,
    job_enqueuer: JobEnqueuer | None = None,
) -> WatcherOrchestrator:
    """Execute a single pass over all watch roots."""

    entry_gateway = entry_gateway or InMemoryEntryStoreGateway()
    fingerprint_reader = (
        fingerprint_reader or entry_gateway
    )  # InMemory gateway satisfies both
    job_enqueuer = job_enqueuer or InfraJobQueueAdapter()
    profiles = build_default_watch_profiles(watch_roots)
    orchestrator = WatcherOrchestrator(
        profiles=profiles,
        entry_reader=fingerprint_reader,
        entry_creator=entry_gateway,
        job_enqueuer=job_enqueuer,
    )
    orchestrator.run_once()
    return orchestrator
