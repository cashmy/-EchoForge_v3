"""EF-03 ExtractionService utilities."""

from .service import (
    DocumentExtractionError,
    DocumentExtractionResult,
    extract_document,
)

__all__ = [
    "DocumentExtractionError",
    "DocumentExtractionResult",
    "extract_document",
]
