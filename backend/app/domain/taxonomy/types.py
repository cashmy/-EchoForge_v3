"""Shared taxonomy domain types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from typing import Any, Dict


class TaxonomyKind(str, Enum):
    """Enumerates supported taxonomy resource types."""

    TYPE = "type"
    DOMAIN = "domain"


@dataclass
class TaxonomyRow:
    """Internal representation of a taxonomy record."""

    id: str
    name: str
    label: str
    description: str | None
    active: bool
    sort_order: int
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    referenced_entries: int = 0

    @property
    def deletion_warning(self) -> bool:
        return not self.active and self.referenced_entries > 0


@dataclass
class TaxonomyListResult:
    items: list[TaxonomyRow]
    page: int
    page_size: int
    total_items: int
    last_updated_cursor: datetime | None


class TaxonomyServiceError(Exception):
    """Domain exception propagated to API handlers."""

    def __init__(
        self,
        *,
        status_code: HTTPStatus,
        error_code: str,
        message: str,
        details: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}


def utcnow() -> datetime:
    """UTC timestamp helper shared across implementations."""

    return datetime.now(timezone.utc)
