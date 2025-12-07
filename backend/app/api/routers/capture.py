"""EF-07 capture endpoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from ...api.dependencies import get_entry_gateway, get_job_enqueuer
from ...domain.ef01_capture.fingerprint import compute_file_fingerprint
from ...domain.ef01_capture.idempotency import evaluate_idempotency
from ...domain.ef01_capture.manual import capture_manual_text
from ...domain.ef01_capture.runtime import InfraJobQueueAdapter
from ...domain.ef06_entrystore.gateway import EntryStoreGateway
from ...infra.logging import get_logger

router = APIRouter(prefix="/api/capture", tags=["capture"])
logger = get_logger(__name__)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".aac"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


class CaptureRequest(BaseModel):
    mode: Literal["text", "file_ref"]
    source_channel: Optional[str] = Field(
        default=None, description="Logical capture channel (defaults per mode)."
    )
    content: Optional[str] = Field(
        default=None, description="Freeform text payload required for mode=text."
    )
    file_path: Optional[str] = Field(
        default=None, description="Filesystem path required for mode=file_ref."
    )
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def _validate_mode_payload(self) -> "CaptureRequest":
        if self.mode == "text":
            if not self.content or not self.content.strip():
                raise ValueError("content is required when mode='text'")
            if self.file_path:
                raise ValueError("file_path must be null when mode='text'")
        else:
            if not self.file_path:
                raise ValueError("file_path is required when mode='file_ref'")
        return self


class CaptureResponse(BaseModel):
    entry_id: str
    ingest_state: str


@router.post(
    "",
    response_model=CaptureResponse,
    status_code=status.HTTP_201_CREATED,
)
def capture_entry(
    payload: CaptureRequest,
    entry_gateway: EntryStoreGateway = Depends(get_entry_gateway),
    job_enqueuer: InfraJobQueueAdapter = Depends(get_job_enqueuer),
) -> CaptureResponse:
    if payload.mode == "text":
        entry = capture_manual_text(
            text=payload.content or "",
            entry_gateway=entry_gateway,
            source_channel=payload.source_channel or "manual_text",
            metadata=payload.metadata,
        )
        logger.info(
            "capture_api_text_accepted",
            extra={"entry_id": entry.entry_id, "source_channel": entry.source_channel},
        )
        return CaptureResponse(
            entry_id=entry.entry_id, ingest_state=entry.pipeline_status
        )

    return _capture_file_reference(payload, entry_gateway, job_enqueuer)


def _capture_file_reference(
    payload: CaptureRequest,
    entry_gateway: EntryStoreGateway,
    job_enqueuer: InfraJobQueueAdapter,
) -> CaptureResponse:
    path = Path(payload.file_path or "").expanduser()
    if not path.exists():
        logger.warning(
            "capture_api_file_missing",
            extra={"file_path": str(path)},
        )
        raise _http_error(
            status.HTTP_400_BAD_REQUEST,
            "EF07-INVALID-REQUEST",
            f"File not found: {path}",
        )

    fingerprint, algorithm = compute_file_fingerprint(path)
    source_channel = payload.source_channel or "api_ingest"
    decision = evaluate_idempotency(entry_gateway, fingerprint, source_channel)
    if not decision.should_process:
        logger.info(
            "capture_api_duplicate",
            extra={
                "existing_entry_id": decision.existing_entry_id,
                "fingerprint": fingerprint,
                "source_channel": source_channel,
            },
        )
        raise _http_error(
            status.HTTP_409_CONFLICT,
            "EF07-CONFLICT",
            "Capture duplicate detected",
            {"entry_id": decision.existing_entry_id},
        )

    source_type = _infer_source_type(path)
    metadata: Dict[str, Any] = dict(payload.metadata or {})
    metadata.setdefault("capture_fingerprint", fingerprint)
    metadata.setdefault("fingerprint_algo", algorithm)
    metadata.setdefault("api_capture_file_path", str(path))

    entry = entry_gateway.create_entry(
        source_type=source_type,
        source_channel=source_channel,
        source_path=str(path),
        metadata=metadata,
        pipeline_status="captured",
    )
    logger.info(
        "capture_api_file_entry_created",
        extra={
            "entry_id": entry.entry_id,
            "source_type": source_type,
            "source_channel": source_channel,
        },
    )

    job_type = "transcription" if source_type == "audio" else "doc_extraction"
    try:
        job_enqueuer.enqueue(
            job_type,
            entry_id=entry.entry_id,
            source_path=str(path),
        )
        logger.info(
            "capture_api_job_enqueued",
            extra={"entry_id": entry.entry_id, "job_type": job_type},
        )
    except Exception:
        logger.exception(
            "capture_api_job_enqueue_failed",
            extra={"entry_id": entry.entry_id, "job_type": job_type},
        )
        raise _http_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "EF07-JOB-ENQUEUE-FAILED",
            "Failed to enqueue downstream job",
            {"entry_id": entry.entry_id},
        )
    queue_status = (
        "queued_for_transcription"
        if job_type == "transcription"
        else "queued_for_extraction"
    )
    entry_gateway.update_pipeline_status(entry.entry_id, pipeline_status=queue_status)
    logger.info(
        "capture_api_entry_status_updated",
        extra={
            "entry_id": entry.entry_id,
            "pipeline_status": queue_status,
        },
    )
    return CaptureResponse(entry_id=entry.entry_id, ingest_state=queue_status)


def _infer_source_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    logger.warning(
        "capture_api_unsupported_extension",
        extra={"extension": ext or ""},
    )
    raise _http_error(
        status.HTTP_400_BAD_REQUEST,
        "EF07-INPUT-UNSUPPORTED",
        f"Unsupported file extension: {ext or '<none>'}",
        {"extension": ext or ""},
    )


def _http_error(
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error_code": error_code,
            "message": message,
            "details": details or {},
        },
    )
