"""Deterministic EF-03 document extraction helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

TEXT_EXTENSIONS: Sequence[str] = (".txt", ".md", ".rtf", ".log")
DOCX_EXTENSIONS: Sequence[str] = (".docx",)
PDF_EXTENSIONS: Sequence[str] = (".pdf",)


@dataclass
class DocumentExtractionResult:
    text: str
    segments: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentExtractionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "internal_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def extract_document(
    source_path: str,
    *,
    mime_type: Optional[str] = None,
    page_range: Optional[str] = None,
    ocr_mode: str = "auto",
    metadata_overrides: Optional[Dict[str, Any]] = None,
) -> DocumentExtractionResult:
    path = Path(source_path)
    _ = metadata_overrides  # reserved for future tuning knobs
    if not path.exists():
        raise DocumentExtractionError(
            f"document not found: {source_path}",
            code="missing_source",
            retryable=False,
        )

    suffix = path.suffix.lower()
    normalized_mime = (mime_type or "").lower()
    page_numbers = _parse_page_range(page_range)

    if suffix in TEXT_EXTENSIONS or normalized_mime in {
        "text/plain",
        "text/markdown",
        "text/x-log",
    }:
        return _extract_plain_text(path, page_numbers=page_numbers)

    if suffix in DOCX_EXTENSIONS or normalized_mime in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        return _extract_docx(path, page_numbers=page_numbers)

    if suffix in PDF_EXTENSIONS or normalized_mime == "application/pdf":
        return _extract_pdf(path, page_numbers=page_numbers, ocr_mode=ocr_mode)

    raise DocumentExtractionError(
        f"unsupported format: {path.suffix or mime_type}",
        code="unsupported_format",
        retryable=False,
    )


def _extract_plain_text(
    path: Path,
    *,
    page_numbers: Optional[List[int]] = None,
) -> DocumentExtractionResult:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        raise DocumentExtractionError(
            "document empty",
            code="doc_empty",
            retryable=False,
        )
    segments = _chunk_text(text, label_prefix="section")
    metadata = {
        "converter": "plain_text",
        "char_count": len(text),
        "page_count": len(segments),
        "segment_count": len(segments),
    }
    return DocumentExtractionResult(text=text, segments=segments, metadata=metadata)


def _extract_docx(
    path: Path,
    *,
    page_numbers: Optional[List[int]] = None,
) -> DocumentExtractionResult:
    try:
        import docx  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise DocumentExtractionError(
            "python-docx is required for .docx extraction",
            code="dependency_missing",
            retryable=False,
        ) from exc

    try:
        document = docx.Document(path)
    except Exception as exc:  # pragma: no cover - docx parser errors
        raise DocumentExtractionError(
            f"failed to parse docx: {exc}",
            code="doc_corrupted",
            retryable=False,
        ) from exc

    paragraphs = [
        para.text.strip() for para in document.paragraphs if para.text.strip()
    ]
    if not paragraphs:
        raise DocumentExtractionError(
            "document empty",
            code="doc_empty",
            retryable=False,
        )
    text = "\n\n".join(paragraphs)
    segments: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(paragraphs):
        segments.append(
            {
                "index": idx,
                "label": f"para_{idx + 1}",
                "text": chunk,
                "char_count": len(chunk),
            }
        )
    metadata = {
        "converter": "python-docx",
        "char_count": len(text),
        "page_count": len(paragraphs),
        "segment_count": len(segments),
    }
    return DocumentExtractionResult(text=text, segments=segments, metadata=metadata)


def _extract_pdf(
    path: Path,
    *,
    page_numbers: Optional[List[int]] = None,
    ocr_mode: str = "auto",
) -> DocumentExtractionResult:
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise DocumentExtractionError(
            "pdfminer.six is required for PDF extraction",
            code="dependency_missing",
            retryable=False,
        ) from exc

    kwargs: Dict[str, Any] = {}
    if page_numbers:
        kwargs["page_numbers"] = page_numbers
    try:
        text = extract_text(str(path), **kwargs)
    except Exception as exc:  # pragma: no cover - pdf parsing errors
        raise DocumentExtractionError(
            f"failed to parse pdf: {exc}",
            code="doc_corrupted",
            retryable=False,
        ) from exc

    normalized = text.strip()
    if not normalized:
        if ocr_mode == "off":
            raise DocumentExtractionError(
                "pdf contains no text layer",
                code="ocr_required",
                retryable=False,
            )
        raise DocumentExtractionError(
            "pdf contains no text layer",
            code="ocr_required",
            retryable=True,
        )

    segments = _segments_from_formfeed(text)
    metadata = {
        "converter": "pdfminer",
        "char_count": len(text),
        "page_count": len(segments),
        "segment_count": len(segments),
        "page_numbers": page_numbers,
    }
    return DocumentExtractionResult(text=text, segments=segments, metadata=metadata)


def _segments_from_formfeed(text: str) -> List[Dict[str, Any]]:
    chunks = [chunk.strip() for chunk in text.split("\f")]
    segments: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        if not chunk:
            continue
        segments.append(
            {
                "index": idx,
                "label": f"page_{idx + 1}",
                "text": chunk,
                "char_count": len(chunk),
            }
        )
    if not segments:
        return [
            {
                "index": 0,
                "label": "page_1",
                "text": text.strip(),
                "char_count": len(text.strip()),
            }
        ]
    return segments


def _chunk_text(text: str, *, label_prefix: str) -> List[Dict[str, Any]]:
    normalized = [chunk.strip() for chunk in re.split(r"\n{2,}", text)]
    segments: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(filter(None, normalized)):
        segments.append(
            {
                "index": idx,
                "label": f"{label_prefix}_{idx + 1}",
                "text": chunk,
                "char_count": len(chunk),
            }
        )
    if not segments:
        segments.append(
            {
                "index": 0,
                "label": f"{label_prefix}_1",
                "text": text.strip(),
                "char_count": len(text.strip()),
            }
        )
    return segments


def _parse_page_range(expression: Optional[str]) -> Optional[List[int]]:
    if not expression:
        return None
    result: List[int] = []
    for token in expression.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_str, end_str = token.split("-", 1)
            try:
                start = int(start_str) - 1
                end = int(end_str) - 1
            except ValueError:
                continue
            if start < 0 or end < start:
                continue
            result.extend(range(start, end + 1))
        else:
            try:
                page = int(token) - 1
            except ValueError:
                continue
            if page < 0:
                continue
            result.append(page)
    deduped = sorted(set(result))
    return deduped or None
