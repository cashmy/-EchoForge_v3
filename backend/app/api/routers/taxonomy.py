"""EF-07 taxonomy endpoints scaffolding (M03-T05 VT01)."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from ...api.dependencies import (
    ActorContext,
    get_actor_context,
    get_taxonomy_service,
)
from ...domain.taxonomy import (
    TaxonomyKind,
    TaxonomyRow,
    TaxonomyService,
    TaxonomyServiceError,
)


class TaxonomyRecord(BaseModel):
    """API representation for a taxonomy row."""

    id: str
    name: str
    label: str
    description: str | None = None
    active: bool = True
    sort_order: int = 500
    metadata: dict[str, Any] | None = None
    deletion_warning: bool | None = None
    referenced_entries: int | None = None


class TaxonomyListResponse(BaseModel):
    """Standard paginated taxonomy payload."""

    items: list[TaxonomyRecord] = Field(default_factory=list)
    page: int = 1
    page_size: int = 50
    total_items: int = 0
    last_updated_cursor: datetime | None = None


class TaxonomyCreateRequest(BaseModel):
    """Request body for POST /api/{resource}."""

    id: str
    label: str
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    metadata: dict[str, Any] | None = None
    active: bool | None = True

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not SLUG_PATTERN.fullmatch(value):
            raise ValueError("id must be a lowercase slug (a-z,0-9,_,-)")
        if len(value) < 3:
            raise ValueError("id must be at least 3 characters")
        return value

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("label is required")
        return value.strip()

    @field_validator("sort_order")
    @classmethod
    def _validate_sort_order(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if not 0 <= value <= 10_000:
            raise ValueError("sort_order must be between 0 and 10000")
        return value


class TaxonomyUpdateRequest(BaseModel):
    """Request body for PATCH /api/{resource}/{id}."""

    label: str | None = None
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    metadata: dict[str, Any] | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def _validate_mutation(self) -> "TaxonomyUpdateRequest":
        if not any(
            value is not None
            for value in (
                self.label,
                self.name,
                self.description,
                self.sort_order,
                self.metadata,
                self.active,
            )
        ):
            raise ValueError("At least one field must be provided")
        return self

    @field_validator("sort_order")
    @classmethod
    def _validate_sort_order(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if not 0 <= value <= 10_000:
            raise ValueError("sort_order must be between 0 and 10000")
        return value


router = APIRouter(prefix="/api", tags=["taxonomy"])


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")

Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
SortBy = Annotated[str | None, Query(pattern="^(sort_order|label|created_at)$")]
SortDir = Annotated[str | None, Query(pattern="^(asc|desc)$")]
ActiveFilter = Annotated[bool | None, Query()]
UpdatedAfter = Annotated[datetime | None, Query()]
SlugId = Annotated[
    str,
    Path(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$",
    ),
]


def _to_record(row: TaxonomyRow) -> TaxonomyRecord:
    return TaxonomyRecord(
        id=row.id,
        name=row.name,
        label=row.label,
        description=row.description,
        active=row.active,
        sort_order=row.sort_order,
        metadata=row.metadata or {},
        deletion_warning=row.deletion_warning or None,
        referenced_entries=row.referenced_entries or None,
    )


def _handle_service_error(exc: TaxonomyServiceError) -> HTTPException:
    return HTTPException(
        status_code=int(exc.status_code),
        detail={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@router.get(
    "/types",
    response_model=TaxonomyListResponse,
    summary="List Entry Types",
)
def list_types(
    page: Page = 1,
    page_size: PageSize = 50,
    sort_by: SortBy = None,
    sort_dir: SortDir = "asc",
    active: ActiveFilter = None,
    updated_after: UpdatedAfter = None,
    service: TaxonomyService = Depends(get_taxonomy_service),
) -> TaxonomyListResponse:
    try:
        result = service.list(
            TaxonomyKind.TYPE,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_dir=sort_dir,
            active=active,
            updated_after=updated_after,
        )
    except TaxonomyServiceError as exc:  # pragma: no cover - defensive
        raise _handle_service_error(exc) from exc
    return TaxonomyListResponse(
        items=[_to_record(row) for row in result.items],
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        last_updated_cursor=result.last_updated_cursor,
    )


@router.post(
    "/types",
    response_model=TaxonomyRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create Entry Type",
)
def create_type(
    payload: TaxonomyCreateRequest,
    service: TaxonomyService = Depends(get_taxonomy_service),
    actor: ActorContext = Depends(get_actor_context),
) -> TaxonomyRecord:
    try:
        row = service.create(
            TaxonomyKind.TYPE,
            payload.model_dump(exclude_none=True),
            actor_id=actor.actor_id,
            actor_source=actor.actor_source,
        )
    except TaxonomyServiceError as exc:
        raise _handle_service_error(exc) from exc
    return _to_record(row)


@router.patch(
    "/types/{type_id}",
    response_model=TaxonomyRecord,
    summary="Update Entry Type",
)
def update_type(
    type_id: SlugId,
    payload: TaxonomyUpdateRequest,
    service: TaxonomyService = Depends(get_taxonomy_service),
    actor: ActorContext = Depends(get_actor_context),
) -> TaxonomyRecord:
    try:
        row = service.update(
            TaxonomyKind.TYPE,
            taxonomy_id=type_id,
            payload=payload.model_dump(exclude_none=True),
            actor_id=actor.actor_id,
            actor_source=actor.actor_source,
        )
    except TaxonomyServiceError as exc:
        raise _handle_service_error(exc) from exc
    return _to_record(row)


@router.delete(
    "/types/{type_id}",
    summary="Delete Entry Type",
)
def delete_type(
    type_id: SlugId,
    service: TaxonomyService = Depends(get_taxonomy_service),
    actor: ActorContext = Depends(get_actor_context),
) -> Response:
    try:
        row = service.delete(
            TaxonomyKind.TYPE,
            taxonomy_id=type_id,
            actor_id=actor.actor_id,
            actor_source=actor.actor_source,
        )
    except TaxonomyServiceError as exc:
        raise _handle_service_error(exc) from exc
    if row.referenced_entries > 0:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "deletion_warning": True,
                "referenced_entries": row.referenced_entries,
            },
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/domains",
    response_model=TaxonomyListResponse,
    summary="List Entry Domains",
)
def list_domains(
    page: Page = 1,
    page_size: PageSize = 50,
    sort_by: SortBy = None,
    sort_dir: SortDir = "asc",
    active: ActiveFilter = None,
    updated_after: UpdatedAfter = None,
    service: TaxonomyService = Depends(get_taxonomy_service),
) -> TaxonomyListResponse:
    try:
        result = service.list(
            TaxonomyKind.DOMAIN,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_dir=sort_dir,
            active=active,
            updated_after=updated_after,
        )
    except TaxonomyServiceError as exc:
        raise _handle_service_error(exc) from exc
    return TaxonomyListResponse(
        items=[_to_record(row) for row in result.items],
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        last_updated_cursor=result.last_updated_cursor,
    )


@router.post(
    "/domains",
    response_model=TaxonomyRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create Entry Domain",
)
def create_domain(
    payload: TaxonomyCreateRequest,
    service: TaxonomyService = Depends(get_taxonomy_service),
    actor: ActorContext = Depends(get_actor_context),
) -> TaxonomyRecord:
    try:
        row = service.create(
            TaxonomyKind.DOMAIN,
            payload.model_dump(exclude_none=True),
            actor_id=actor.actor_id,
            actor_source=actor.actor_source,
        )
    except TaxonomyServiceError as exc:
        raise _handle_service_error(exc) from exc
    return _to_record(row)


@router.patch(
    "/domains/{domain_id}",
    response_model=TaxonomyRecord,
    summary="Update Entry Domain",
)
def update_domain(
    domain_id: SlugId,
    payload: TaxonomyUpdateRequest,
    service: TaxonomyService = Depends(get_taxonomy_service),
    actor: ActorContext = Depends(get_actor_context),
) -> TaxonomyRecord:
    try:
        row = service.update(
            TaxonomyKind.DOMAIN,
            taxonomy_id=domain_id,
            payload=payload.model_dump(exclude_none=True),
            actor_id=actor.actor_id,
            actor_source=actor.actor_source,
        )
    except TaxonomyServiceError as exc:
        raise _handle_service_error(exc) from exc
    return _to_record(row)


@router.delete(
    "/domains/{domain_id}",
    summary="Delete Entry Domain",
)
def delete_domain(
    domain_id: SlugId,
    service: TaxonomyService = Depends(get_taxonomy_service),
    actor: ActorContext = Depends(get_actor_context),
) -> Response:
    try:
        row = service.delete(
            TaxonomyKind.DOMAIN,
            taxonomy_id=domain_id,
            actor_id=actor.actor_id,
            actor_source=actor.actor_source,
        )
    except TaxonomyServiceError as exc:
        raise _handle_service_error(exc) from exc
    if row.referenced_entries > 0:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "deletion_warning": True,
                "referenced_entries": row.referenced_entries,
            },
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
