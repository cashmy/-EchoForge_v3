"""Canonical EF-06 pipeline state helpers.

Derived from EF06_EntryStore_Addendum_v1.2 and used to keep
`ingest_state` and `pipeline_status` combinations consistent across
workers (EF-02 → EF-05) and governance tooling.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class PipelinePhase:
    """Defines a coarse ingest state and its allowed pipeline statuses."""

    key: str
    ingest_state: str
    pipeline_statuses: Tuple[str, ...]
    description: str


DEFAULT_INGEST_STATE = "captured"


PIPELINE_STATUS = SimpleNamespace(
    CAPTURED="captured",
    INGESTED="ingested",
    QUEUED_FOR_TRANSCRIPTION="queued_for_transcription",
    TRANSCRIPTION_IN_PROGRESS="transcription_in_progress",
    TRANSCRIPTION_COMPLETE="transcription_complete",
    TRANSCRIPTION_FAILED="transcription_failed",
    QUEUED_FOR_EXTRACTION="queued_for_extraction",
    EXTRACTION_IN_PROGRESS="extraction_in_progress",
    EXTRACTION_COMPLETE="extraction_complete",
    EXTRACTION_FAILED="extraction_failed",
    QUEUED_FOR_NORMALIZATION="queued_for_normalization",
    NORMALIZATION_IN_PROGRESS="normalization_in_progress",
    NORMALIZATION_COMPLETE="normalization_complete",
    NORMALIZATION_FAILED="normalization_failed",
    QUEUED_FOR_SEMANTICS="queued_for_semantics",
    SEMANTIC_IN_PROGRESS="semantic_in_progress",
    SEMANTIC_COMPLETE="semantic_complete",
    SEMANTIC_FAILED="semantic_failed",
)


PIPELINE_PHASES: Tuple[PipelinePhase, ...] = (
    PipelinePhase(
        key="capture",
        ingest_state="captured",
        pipeline_statuses=("captured", "ingested"),
        description="Entry accepted by EF-01/API but not yet queued.",
    ),
    PipelinePhase(
        key="audio_queue",
        ingest_state="queued_for_transcription",
        pipeline_statuses=("queued_for_transcription",),
        description="Audio entry queued for EF-02.",
    ),
    PipelinePhase(
        key="audio_processing",
        ingest_state="processing_transcription",
        pipeline_statuses=("transcription_in_progress",),
        description="EF-02 actively producing a transcript.",
    ),
    PipelinePhase(
        key="document_queue",
        ingest_state="queued_for_extraction",
        pipeline_statuses=("queued_for_extraction",),
        description="Document entry queued for EF-03.",
    ),
    PipelinePhase(
        key="document_processing",
        ingest_state="processing_extraction",
        pipeline_statuses=("extraction_in_progress",),
        description="EF-03 actively extracting or running OCR.",
    ),
    PipelinePhase(
        key="normalization_intake_audio",
        ingest_state="processing_normalization",
        pipeline_statuses=("transcription_complete", "queued_for_normalization"),
        description="EF-02 succeeded; EF-04 not started yet.",
    ),
    PipelinePhase(
        key="normalization_intake_document",
        ingest_state="processing_normalization",
        pipeline_statuses=("extraction_complete", "queued_for_normalization"),
        description="EF-03 succeeded; EF-04 not started yet.",
    ),
    PipelinePhase(
        key="normalization_processing",
        ingest_state="processing_normalization",
        pipeline_statuses=("normalization_in_progress",),
        description="EF-04 currently normalizing text.",
    ),
    PipelinePhase(
        key="semantic_intake",
        ingest_state="processing_semantic",
        pipeline_statuses=("normalization_complete", "queued_for_semantics"),
        description="EF-04 succeeded; EF-05 pending.",
    ),
    PipelinePhase(
        key="semantic_processing",
        ingest_state="processing_semantic",
        pipeline_statuses=("semantic_in_progress",),
        description="EF-05 running semantic enrichment.",
    ),
    PipelinePhase(
        key="completed",
        ingest_state="processed",
        pipeline_statuses=("semantic_complete", "normalization_complete"),
        description="Terminal success (semantic may be skipped).",
    ),
    PipelinePhase(
        key="failure",
        ingest_state="failed",
        pipeline_statuses=(
            "transcription_failed",
            "extraction_failed",
            "normalization_failed",
            "semantic_failed",
        ),
        description="Terminal failure. Stage-specific code lives in pipeline_status.",
    ),
)
PIPELINE_STATUS_TRANSITIONS: Dict[str, Dict[str, str]] = {
    "captured": {
        "captured": "captured",
        "ingested": "captured",
        "queued_for_transcription": "queued_for_transcription",
        "queued_for_extraction": "queued_for_extraction",
    },
    "queued_for_transcription": {
        "queued_for_transcription": "queued_for_transcription",
        "transcription_in_progress": "processing_transcription",
        "transcription_failed": "failed",
    },
    "processing_transcription": {
        "transcription_in_progress": "processing_transcription",
        "transcription_failed": "failed",
        "transcription_complete": "processing_normalization",
        "queued_for_normalization": "processing_normalization",
        "queued_for_transcription": "queued_for_transcription",
    },
    "queued_for_extraction": {
        "queued_for_extraction": "queued_for_extraction",
        "extraction_in_progress": "processing_extraction",
        "extraction_failed": "failed",
    },
    "processing_extraction": {
        "extraction_in_progress": "processing_extraction",
        "extraction_failed": "failed",
        "extraction_complete": "processing_normalization",
        "queued_for_normalization": "processing_normalization",
        "queued_for_extraction": "queued_for_extraction",
    },
    "processing_normalization": {
        "transcription_complete": "processing_normalization",
        "extraction_complete": "processing_normalization",
        "queued_for_normalization": "processing_normalization",
        "normalization_in_progress": "processing_normalization",
        "normalization_complete": "processing_semantic",
        "normalization_failed": "failed",
    },
    "processing_semantic": {
        "normalization_complete": "processing_semantic",
        "queued_for_semantics": "processing_semantic",
        "semantic_in_progress": "processing_semantic",
        "semantic_failed": "failed",
        "semantic_complete": "processed",
    },
    "processed": {
        "semantic_complete": "processed",
        "normalization_complete": "processed",
    },
    "failed": {
        "transcription_failed": "failed",
        "extraction_failed": "failed",
        "normalization_failed": "failed",
        "semantic_failed": "failed",
    },
}


def _build_transition_targets(
    transitions: Dict[str, Dict[str, str]],
) -> Dict[str, Tuple[str, ...]]:
    adjacency: Dict[str, List[str]] = defaultdict(list)
    for source_state, mapping in transitions.items():
        targets = adjacency.setdefault(source_state, [])
        for status, dest_state in mapping.items():
            if status not in targets:
                targets.append(status)
    return {state: tuple(values) for state, values in adjacency.items()}


INGEST_STATE_TO_PIPELINE_STATUSES = _build_transition_targets(
    PIPELINE_STATUS_TRANSITIONS
)


def _derive_ingest_adjacency(
    transitions: Dict[str, Dict[str, str]],
) -> Dict[str, Tuple[str, ...]]:
    adjacency: Dict[str, List[str]] = defaultdict(list)
    for source_state, mapping in transitions.items():
        for dest_state in mapping.values():
            if dest_state == source_state:
                continue
            if dest_state not in adjacency[source_state]:
                adjacency[source_state].append(dest_state)
    return {state: tuple(values) for state, values in adjacency.items()}


VALID_INGEST_TRANSITIONS: Dict[str, Tuple[str, ...]] = _derive_ingest_adjacency(
    PIPELINE_STATUS_TRANSITIONS
)

AUDIO_INGEST_FLOW: Tuple[str, ...] = (
    "captured",
    "queued_for_transcription",
    "processing_transcription",
    "processing_normalization",
    "processing_semantic",
    "processed",
)

DOCUMENT_INGEST_FLOW: Tuple[str, ...] = (
    "captured",
    "queued_for_extraction",
    "processing_extraction",
    "processing_normalization",
    "processing_semantic",
    "processed",
)

FAILURE_STATE: str = "failed"
# Shared constant for the terminal failure state.


def resolve_next_ingest_state(
    current_ingest_state: str,
    pipeline_status: str,
) -> str:
    """Return the ingest_state that results from applying pipeline_status."""

    state = current_ingest_state or DEFAULT_INGEST_STATE
    rules = PIPELINE_STATUS_TRANSITIONS.get(state)
    if rules and pipeline_status in rules:
        return rules[pipeline_status]
    raise ValueError(
        f"pipeline_status '{pipeline_status}' is not allowed when ingest_state='{state}'"
    )


def allowed_pipeline_statuses(ingest_state: str) -> Tuple[str, ...]:
    """Return the valid pipeline_status values for the provided ingest_state."""

    return INGEST_STATE_TO_PIPELINE_STATUSES.get(ingest_state, tuple())
