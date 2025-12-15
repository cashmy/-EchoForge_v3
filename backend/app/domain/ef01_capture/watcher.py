"""Watcher orchestration helpers for EF-01."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Protocol

from .fingerprint import compute_file_fingerprint
from .idempotency import EntryFingerprintReader, evaluate_idempotency
from .watch_folders import WATCH_SUBDIRECTORIES, ensure_watch_root_layout
from ..ef06_entrystore.models import Entry
from ...infra.logging import get_logger

__all__ = [
    "EntryCreator",
    "JobEnqueuer",
    "WatchProfile",
    "WatcherOrchestrator",
    "build_default_watch_profiles",
]

logger = get_logger(__name__)


class EntryCreator(Protocol):  # pragma: no cover - structural typing hook
    """Subset of EF-06 functionality EF-01 watcher needs."""

    def create_entry(
        self,
        *,
        source_type: str,
        source_channel: str,
        source_path: str,
        metadata: Dict[str, object],
        pipeline_status: str,
        display_title: Optional[str] = None,
    ) -> Entry: ...

    def update_pipeline_status(
        self, entry_id: str, *, pipeline_status: str
    ) -> Entry: ...


class JobEnqueuer(Protocol):  # pragma: no cover - structural typing hook
    """Interface to INF-02 job queue."""

    def enqueue(
        self,
        job_type: str,
        *,
        entry_id: str,
        source_path: str,
    ) -> None: ...


@dataclass(frozen=True)
class WatchProfile:
    """Configuration describing how a watch root should behave."""

    root: Path
    source_type: str
    source_channel: str
    job_type: str


def build_default_watch_profiles(
    watch_roots: Iterable[str | Path],
) -> list[WatchProfile]:
    """Infer audio/document profiles based on watch root names."""

    profiles: list[WatchProfile] = []
    for root in watch_roots:
        root_path = Path(root).expanduser()
        name = root_path.name.lower()
        if "audio" in name or "voice" in name:
            profiles.append(
                WatchProfile(
                    root=root_path,
                    source_type="audio",
                    source_channel="watch_folder_audio",
                    job_type="transcription",
                )
            )
        else:
            profiles.append(
                WatchProfile(
                    root=root_path,
                    source_type="document",
                    source_channel="watch_folder_document",
                    job_type="doc_extraction",
                )
            )
    return profiles


@dataclass
class WatcherOrchestrator:
    """Coordinates EF-01 watch folder ingestion logic."""

    profiles: list[WatchProfile]
    entry_reader: EntryFingerprintReader
    entry_creator: EntryCreator
    job_enqueuer: JobEnqueuer

    def run_once(self) -> None:
        for profile in self.profiles:
            ensure_watch_root_layout(profile.root)
            incoming_dir = profile.root / WATCH_SUBDIRECTORIES[0]
            for candidate in incoming_dir.iterdir():
                if not candidate.is_file():
                    continue
                fingerprint, algorithm = compute_file_fingerprint(candidate)
                decision = evaluate_idempotency(
                    self.entry_reader, fingerprint, profile.source_channel
                )
                if not decision.should_process:
                    logger.info(
                        "watcher_skip_duplicate",
                        extra={
                            "entry_id": decision.existing_entry_id,
                            "fingerprint": fingerprint,
                            "source_channel": profile.source_channel,
                        },
                    )
                    continue
                processing_dir = profile.root / WATCH_SUBDIRECTORIES[1]
                processing_dir.mkdir(parents=True, exist_ok=True)
                destination = processing_dir / candidate.name
                shutil.move(candidate, destination)
                logger.info(
                    "watcher_file_moved",
                    extra={
                        "source": str(candidate),
                        "destination": str(destination),
                        "source_channel": profile.source_channel,
                    },
                )
                metadata = {
                    "capture_fingerprint": fingerprint,
                    "fingerprint_algo": algorithm,
                }
                record = self.entry_creator.create_entry(
                    source_type=profile.source_type,
                    source_channel=profile.source_channel,
                    source_path=str(destination),
                    metadata=metadata,
                    pipeline_status="captured",
                )
                logger.info(
                    "watcher_entry_created",
                    extra={
                        "entry_id": record.entry_id,
                        "source_channel": profile.source_channel,
                        "job_type": profile.job_type,
                    },
                )
                if profile.job_type == "transcription":
                    queue_status = "queued_for_transcription"
                elif profile.job_type == "doc_extraction":
                    queue_status = "queued_for_extraction"
                else:
                    queue_status = "queued"
                try:
                    self.job_enqueuer.enqueue(
                        profile.job_type,
                        entry_id=record.entry_id,
                        source_path=str(destination),
                    )
                    logger.info(
                        "watcher_job_enqueued",
                        extra={
                            "entry_id": record.entry_id,
                            "job_type": profile.job_type,
                        },
                    )
                except Exception:
                    logger.exception(
                        "watcher_job_enqueue_failed",
                        extra={
                            "entry_id": record.entry_id,
                            "job_type": profile.job_type,
                            "source_path": str(destination),
                        },
                    )
                    raise
                self.entry_creator.update_pipeline_status(
                    record.entry_id, pipeline_status=queue_status
                )
                logger.info(
                    "watcher_entry_status_updated",
                    extra={
                        "entry_id": record.entry_id,
                        "pipeline_status": queue_status,
                    },
                )
