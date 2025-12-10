"""Dashboard summary endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ...domain.dashboard import DashboardSummaryService
from ...infra.logging import get_logger
from ...infra.metrics import get_metrics_client

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = get_logger(__name__)
metrics = get_metrics_client()
_summary_service = DashboardSummaryService()


class FailureWindow(BaseModel):
    since: datetime
    counts: dict[str, int] = Field(default_factory=dict)


class PipelineSection(BaseModel):
    total: int
    by_ingest_state: dict[str, int] = Field(default_factory=dict)
    failure_window: FailureWindow


class NeedsReviewItem(BaseModel):
    entry_id: str
    display_title: str | None = None
    pipeline_status: str
    cognitive_status: str | None = None
    updated_at: datetime


class NeedsReviewSection(BaseModel):
    items: list[NeedsReviewItem] = Field(default_factory=list)


class CognitiveSection(BaseModel):
    by_status: dict[str, int] = Field(default_factory=dict)
    needs_review: NeedsReviewSection


class DailyCount(BaseModel):
    date: date
    count: int


class SourceMixItem(BaseModel):
    source_channel: str
    count: int


class MomentumSection(BaseModel):
    recent_intake: list[DailyCount] = Field(default_factory=list)
    source_mix: list[SourceMixItem] = Field(default_factory=list)


class TaxonomyLeaderboardItem(BaseModel):
    id: str | None = None
    label: str | None = None
    count: int


class TaxonomySection(BaseModel):
    top_types: list[TaxonomyLeaderboardItem] = Field(default_factory=list)
    top_domains: list[TaxonomyLeaderboardItem] = Field(default_factory=list)


class RecentItem(BaseModel):
    entry_id: str
    display_title: str | None = None
    pipeline_status: str
    updated_at: datetime


class RecentSection(BaseModel):
    processed: list[RecentItem] = Field(default_factory=list)


class DashboardMeta(BaseModel):
    generated_at: datetime
    time_window_days: int
    failure_window_days: int
    source_window_days: int
    include_archived: bool = False


class DashboardSummaryResponse(BaseModel):
    pipeline: PipelineSection
    cognitive: CognitiveSection
    momentum: MomentumSection
    taxonomy: TaxonomySection
    recent: RecentSection
    meta: DashboardMeta


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Aggregate EntryStore pipeline metrics for dashboard widgets",
)
def get_dashboard_summary(
    time_window_days: Annotated[int | None, Query(ge=1, le=30)] = None,
    include_archived: bool = Query(False, description="Include archived entries."),
) -> DashboardSummaryResponse:
    """Return the dashboard summary payload."""

    metrics.increment("dashboard_summary_http_total")
    payload = _summary_service.build_summary(
        time_window_days=time_window_days,
        include_archived=include_archived,
    )
    logger.debug(
        "dashboard_summary_payload",
        extra={
            "time_window_days": time_window_days,
            "include_archived": include_archived,
        },
    )
    return DashboardSummaryResponse.model_validate(payload)
