"""Aggregation helpers for `/api/dashboard/summary`."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict
import time

from sqlalchemy import MetaData, String, Table, cast, func, literal, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.sql import Select

from ...infra.db import ENGINE
from ...infra.logging import get_logger
from ...infra.metrics import MetricsClient, get_metrics_client
from ..ef06_entrystore.pipeline_states import (
    DEFAULT_INGEST_STATE,
    INGEST_STATE_TO_PIPELINE_STATUSES,
    PIPELINE_PHASES,
)

logger = get_logger(__name__)

DEFAULT_TIME_WINDOW_DAYS = 7
MAX_TIME_WINDOW_DAYS = 30
FAILURE_WINDOW_DAYS = 7
SOURCE_WINDOW_DAYS = 30
NEEDS_REVIEW_LIMIT = 10
RECENT_PROCESSED_LIMIT = 5
SOURCE_MIX_LIMIT = 8
TAXONOMY_LIMIT = 5
NEEDS_REVIEW_COGNITIVE_STATUSES: tuple[str, ...] = (
    "unreviewed",
    "review_needed",
)
FAILURE_PIPELINE_STATUSES: tuple[str, ...] = tuple(
    INGEST_STATE_TO_PIPELINE_STATUSES.get("failed", tuple())
)
NEEDS_REVIEW_INGEST_STATES: tuple[str, ...] = (
    "processing_semantic",
    "processed",
)


class DashboardSummaryService:
    """Aggregates EntryStore rows into dashboard-friendly slices."""

    def __init__(
        self,
        *,
        engine: Engine | None = None,
        default_time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
        max_time_window_days: int = MAX_TIME_WINDOW_DAYS,
        failure_window_days: int = FAILURE_WINDOW_DAYS,
        source_window_days: int = SOURCE_WINDOW_DAYS,
        metrics: MetricsClient | None = None,
    ) -> None:
        self._engine = engine or ENGINE
        self._metadata = MetaData()
        self._entries = self._load_required_table("entries")
        self._types = self._load_optional_table("entry_types")
        self._domains = self._load_optional_table("entry_domains")
        self._is_archived_col = getattr(self._entries.c, "is_archived", None)
        self._type_id_col = getattr(self._entries.c, "type_id", None)
        self._type_label_col = getattr(self._entries.c, "type_label", None)
        self._domain_id_col = getattr(self._entries.c, "domain_id", None)
        self._domain_label_col = getattr(self._entries.c, "domain_label", None)
        self._default_time_window_days = default_time_window_days
        self._max_time_window_days = max_time_window_days
        self._failure_window_days = failure_window_days
        self._source_window_days = source_window_days
        self._metrics = metrics or get_metrics_client()
        self._status_to_ingest = self._build_status_index()
        self._needs_review_statuses = self._collect_statuses(NEEDS_REVIEW_INGEST_STATES)
        self._processed_statuses = self._collect_statuses(("processed",))

    def build_summary(
        self,
        *,
        time_window_days: int | None = None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        window_days = self._normalize_window(time_window_days)
        now = datetime.now(timezone.utc)
        failure_since = now - timedelta(days=self._failure_window_days)
        source_since = now - timedelta(days=self._source_window_days)
        self._metrics.increment("dashboard_summary_requests_total")
        start = time.perf_counter()
        with self._engine.begin() as conn:
            pipeline_counts = self._fetch_pipeline_counts(conn, include_archived)
            cognitive_counts = self._fetch_cognitive_counts(conn, include_archived)
            failure_counts = self._fetch_failure_counts(
                conn, include_archived, failure_since
            )
            needs_review_items = self._fetch_needs_review_items(conn, include_archived)
            recent_processed = self._fetch_recent_processed(conn, include_archived)
            recent_intake = self._fetch_recent_intake(
                conn, include_archived, window_days, now
            )
            source_mix = self._fetch_source_mix(conn, include_archived, source_since)
            top_types = self._fetch_taxonomy_leaderboard(
                conn, include_archived, kind="type"
            )
            top_domains = self._fetch_taxonomy_leaderboard(
                conn, include_archived, kind="domain"
            )
        duration_ms = int((time.perf_counter() - start) * 1000)
        self._metrics.gauge("dashboard_summary_last_duration_ms", duration_ms)
        logger.info(
            "dashboard_summary_generated",
            extra={
                "duration_ms": duration_ms,
                "time_window_days": window_days,
                "include_archived": include_archived,
            },
        )
        total_pipeline = sum(pipeline_counts.values())
        return {
            "pipeline": {
                "total": total_pipeline,
                "by_ingest_state": pipeline_counts,
                "failure_window": {
                    "since": failure_since,
                    "counts": failure_counts,
                },
            },
            "cognitive": {
                "by_status": cognitive_counts,
                "needs_review": {"items": needs_review_items},
            },
            "momentum": {
                "recent_intake": recent_intake,
                "source_mix": source_mix,
            },
            "taxonomy": {
                "top_types": top_types,
                "top_domains": top_domains,
            },
            "recent": {
                "processed": recent_processed,
            },
            "meta": {
                "generated_at": now,
                "time_window_days": window_days,
                "failure_window_days": self._failure_window_days,
                "source_window_days": self._source_window_days,
                "include_archived": include_archived,
            },
        }

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def _fetch_pipeline_counts(
        self,
        conn,
        include_archived: bool,
    ) -> dict[str, int]:
        stmt = select(
            self._entries.c.pipeline_status.label("status"),
            func.count().label("count"),
        )
        stmt = stmt.select_from(self._entries)
        stmt = self._apply_active_filter(stmt, include_archived)
        stmt = stmt.group_by(self._entries.c.pipeline_status)
        rows = conn.execute(stmt).mappings().all()
        counts: Dict[str, int] = defaultdict(int)
        for row in rows:
            status = row["status"] or ""
            ingest_state = self._status_to_ingest.get(status, DEFAULT_INGEST_STATE)
            counts[ingest_state] += int(row["count"])
        return dict(sorted(counts.items()))

    def _fetch_cognitive_counts(self, conn, include_archived: bool) -> dict[str, int]:
        stmt = select(
            self._entries.c.cognitive_status.label("status"),
            func.count().label("count"),
        )
        stmt = stmt.select_from(self._entries)
        stmt = self._apply_active_filter(stmt, include_archived)
        stmt = stmt.group_by(self._entries.c.cognitive_status)
        rows = conn.execute(stmt).mappings().all()
        counts: Dict[str, int] = {}
        for row in rows:
            status = row["status"] or "unknown"
            counts[status] = int(row["count"])
        return counts

    def _fetch_failure_counts(
        self,
        conn,
        include_archived: bool,
        failure_since: datetime,
    ) -> dict[str, int]:
        if not FAILURE_PIPELINE_STATUSES:
            return {}
        stmt = select(
            self._entries.c.pipeline_status.label("status"),
            func.count().label("count"),
        )
        stmt = stmt.select_from(self._entries)
        stmt = stmt.where(
            self._entries.c.pipeline_status.in_(FAILURE_PIPELINE_STATUSES),
            self._entries.c.updated_at >= failure_since,
        )
        stmt = self._apply_active_filter(stmt, include_archived)
        stmt = stmt.group_by(self._entries.c.pipeline_status)
        rows = conn.execute(stmt).mappings().all()
        return {row["status"]: int(row["count"]) for row in rows}

    def _fetch_needs_review_items(
        self, conn, include_archived: bool
    ) -> list[dict[str, Any]]:
        stmt = select(
            self._entries.c.entry_id,
            self._entries.c.display_title,
            self._entries.c.summary,
            self._entries.c.pipeline_status,
            self._entries.c.cognitive_status,
            self._entries.c.updated_at,
        )
        stmt = stmt.where(
            self._entries.c.cognitive_status.in_(NEEDS_REVIEW_COGNITIVE_STATUSES),
            self._entries.c.pipeline_status.in_(self._needs_review_statuses),
        )
        stmt = self._apply_active_filter(stmt, include_archived)
        stmt = stmt.order_by(self._entries.c.updated_at.desc())
        stmt = stmt.limit(NEEDS_REVIEW_LIMIT)
        rows = conn.execute(stmt).mappings().all()
        items: list[dict[str, Any]] = []
        for row in rows:
            title = row["display_title"] or row["summary"]
            items.append(
                {
                    "entry_id": row["entry_id"],
                    "display_title": title,
                    "pipeline_status": row["pipeline_status"],
                    "cognitive_status": row["cognitive_status"],
                    "updated_at": row["updated_at"],
                }
            )
        return items

    def _fetch_recent_processed(
        self,
        conn,
        include_archived: bool,
    ) -> list[dict[str, Any]]:
        stmt = select(
            self._entries.c.entry_id,
            self._entries.c.display_title,
            self._entries.c.summary,
            self._entries.c.pipeline_status,
            self._entries.c.updated_at,
        )
        stmt = stmt.where(self._entries.c.pipeline_status.in_(self._processed_statuses))
        stmt = self._apply_active_filter(stmt, include_archived)
        stmt = stmt.order_by(self._entries.c.updated_at.desc())
        stmt = stmt.limit(RECENT_PROCESSED_LIMIT)
        rows = conn.execute(stmt).mappings().all()
        items: list[dict[str, Any]] = []
        for row in rows:
            title = row["display_title"] or row["summary"]
            items.append(
                {
                    "entry_id": row["entry_id"],
                    "display_title": title,
                    "pipeline_status": row["pipeline_status"],
                    "updated_at": row["updated_at"],
                }
            )
        return items

    def _fetch_recent_intake(
        self,
        conn,
        include_archived: bool,
        days: int,
        now: datetime,
    ) -> list[dict[str, Any]]:
        start_dt = now - timedelta(days=days - 1)
        bucket = cast(func.date(self._entries.c.created_at), String).label("bucket")
        count_expr = func.count().label("count")
        stmt = select(bucket, count_expr)
        stmt = stmt.select_from(self._entries)
        stmt = stmt.where(self._entries.c.created_at >= start_dt)
        stmt = self._apply_active_filter(stmt, include_archived)
        stmt = stmt.group_by(bucket)
        stmt = stmt.order_by(bucket.asc())
        rows = conn.execute(stmt).mappings().all()
        mapped_counts = {}
        for row in rows:
            bucket_value = row["bucket"]
            if bucket_value is None:
                continue
            if isinstance(bucket_value, datetime):
                key = bucket_value.date()
            elif isinstance(bucket_value, date):
                key = bucket_value
            else:
                key = date.fromisoformat(str(bucket_value))
            mapped_counts[key] = int(row["count"])
        series: list[dict[str, Any]] = []
        for offset in range(days):
            bucket_date = (start_dt + timedelta(days=offset)).date()
            series.append(
                {"date": bucket_date, "count": mapped_counts.get(bucket_date, 0)}
            )
        return series

    def _fetch_source_mix(
        self,
        conn,
        include_archived: bool,
        since: datetime,
    ) -> list[dict[str, Any]]:
        channel = func.coalesce(self._entries.c.source_channel, literal("unknown"))
        count_expr = func.count().label("count")
        stmt = select(channel.label("channel"), count_expr)
        stmt = stmt.select_from(self._entries)
        stmt = stmt.where(self._entries.c.created_at >= since)
        stmt = self._apply_active_filter(stmt, include_archived)
        stmt = stmt.group_by(channel)
        stmt = stmt.order_by(count_expr.desc())
        rows = conn.execute(stmt).mappings().all()
        items: list[dict[str, Any]] = []
        remaining = 0
        for idx, row in enumerate(rows):
            count = int(row["count"])
            if idx < SOURCE_MIX_LIMIT:
                items.append({"source_channel": row["channel"], "count": count})
            else:
                remaining += count
        if remaining > 0:
            items.append({"source_channel": "OTHER", "count": remaining})
        return items

    def _fetch_taxonomy_leaderboard(
        self,
        conn,
        include_archived: bool,
        *,
        kind: str,
    ) -> list[dict[str, Any]]:
        if kind == "type":
            id_col = self._type_id_col
            label_col = self._type_label_col
            table = self._types
        else:
            id_col = self._domain_id_col
            label_col = self._domain_label_col
            table = self._domains
        if id_col is None:
            return []
        base = self._entries
        if table is not None:
            join_target = base.outerjoin(table, id_col == table.c.id)
            resolved_label = func.coalesce(table.c.label, label_col)
        else:
            join_target = base
            resolved_label = label_col
        count_expr = func.count().label("count")
        stmt = select(
            id_col.label("id"),
            resolved_label.label("label"),
            count_expr,
        )
        stmt = stmt.select_from(join_target)
        stmt = stmt.where(id_col.is_not(None))
        stmt = self._apply_active_filter(stmt, include_archived)
        stmt = stmt.group_by(id_col, resolved_label)
        stmt = stmt.order_by(count_expr.desc(), resolved_label.asc())
        stmt = stmt.limit(TAXONOMY_LIMIT)
        rows = conn.execute(stmt).mappings().all()
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "label": row["label"],
                    "count": int(row["count"]),
                }
            )
        return results

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _normalize_window(self, window: int | None) -> int:
        base = window or self._default_time_window_days
        return max(1, min(base, self._max_time_window_days))

    def _apply_active_filter(self, stmt: Select, include_archived: bool) -> Select:
        if include_archived or self._is_archived_col is None:
            return stmt
        return stmt.where(self._is_archived_col.is_(False))

    def _load_required_table(self, name: str) -> Table:
        try:
            return Table(name, self._metadata, autoload_with=self._engine)
        except NoSuchTableError as exc:  # pragma: no cover - schema misconfig
            raise RuntimeError(f"Required table '{name}' not found") from exc

    def _load_optional_table(self, name: str) -> Table | None:
        try:
            return Table(name, self._metadata, autoload_with=self._engine)
        except NoSuchTableError:
            logger.warning("dashboard_table_missing", extra={"table": name})
            return None

    def _build_status_index(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for phase in PIPELINE_PHASES:
            for status in phase.pipeline_statuses:
                mapping[status] = phase.ingest_state
        return mapping

    def _collect_statuses(self, ingest_states: tuple[str, ...]) -> tuple[str, ...]:
        statuses: set[str] = set()
        for state in ingest_states:
            statuses.update(INGEST_STATE_TO_PIPELINE_STATUSES.get(state, tuple()))
        return tuple(sorted(statuses))
