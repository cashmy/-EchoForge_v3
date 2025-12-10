"""Tests for dashboard summary aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from backend.app.domain.dashboard import DashboardSummaryService
from backend.app.domain.dashboard.summary_service import MAX_TIME_WINDOW_DAYS


def _setup_schema():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = sa.MetaData()
    entries = sa.Table(
        "entries",
        metadata,
        sa.Column("entry_id", sa.String(length=64), primary_key=True),
        sa.Column("pipeline_status", sa.String(length=64), nullable=False),
        sa.Column("cognitive_status", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("display_title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_channel", sa.String(length=128), nullable=True),
        sa.Column("type_id", sa.String(length=128), nullable=True),
        sa.Column("type_label", sa.String(length=128), nullable=True),
        sa.Column("domain_id", sa.String(length=128), nullable=True),
        sa.Column("domain_label", sa.String(length=128), nullable=True),
    )
    entry_types = sa.Table(
        "entry_types",
        metadata,
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("label", sa.String(length=128), nullable=False),
    )
    entry_domains = sa.Table(
        "entry_domains",
        metadata,
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("label", sa.String(length=128), nullable=False),
    )
    metadata.create_all(engine)
    return engine, entries, entry_types, entry_domains


def _entry_row(
    *,
    entry_id: str,
    pipeline_status: str,
    ingest_state: str,
    cognitive_status: str,
    created_at: datetime,
    updated_at: datetime,
    source_channel: str,
    type_id: str | None,
    type_label: str | None,
    domain_id: str | None,
    domain_label: str | None,
    display_title: str | None = None,
    summary: str | None = None,
) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "pipeline_status": pipeline_status,
        "cognitive_status": cognitive_status,
        "metadata": {"capture_metadata": {"ingest_state": ingest_state}},
        "created_at": created_at,
        "updated_at": updated_at,
        "display_title": display_title,
        "summary": summary,
        "source_channel": source_channel,
        "type_id": type_id,
        "type_label": type_label,
        "domain_id": domain_id,
        "domain_label": domain_label,
    }


def test_build_summary_returns_expected_sections():
    engine, entries, entry_types, entry_domains = _setup_schema()
    now = datetime(2025, 12, 10, 12, 0, tzinfo=timezone.utc)
    with engine.begin() as conn:
        conn.execute(
            entry_types.insert(),
            [
                {"id": "idea", "label": "Idea"},
                {"id": "note", "label": "Note"},
            ],
        )
        conn.execute(
            entry_domains.insert(),
            [
                {"id": "architecture", "label": "Architecture"},
            ],
        )
        conn.execute(
            entries.insert(),
            [
                _entry_row(
                    entry_id="processed-1",
                    pipeline_status="semantic_complete",
                    ingest_state="processed",
                    cognitive_status="complete",
                    created_at=now - timedelta(days=1),
                    updated_at=now - timedelta(hours=2),
                    source_channel="watch_audio",
                    type_id="idea",
                    type_label="Idea",
                    domain_id="architecture",
                    domain_label="Architecture",
                    display_title="Processed Entry",
                    summary="Processed summary",
                ),
                _entry_row(
                    entry_id="needs-review",
                    pipeline_status="semantic_in_progress",
                    ingest_state="processing_semantic",
                    cognitive_status="review_needed",
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(hours=1),
                    source_channel="watch_documents",
                    type_id="note",
                    type_label="Note",
                    domain_id="architecture",
                    domain_label="Architecture",
                    display_title=None,
                    summary="Needs attention",
                ),
                _entry_row(
                    entry_id="failed-one",
                    pipeline_status="transcription_failed",
                    ingest_state="failed",
                    cognitive_status="unreviewed",
                    created_at=now - timedelta(days=3),
                    updated_at=now - timedelta(hours=5),
                    source_channel="watch_audio",
                    type_id="idea",
                    type_label="Idea",
                    domain_id="architecture",
                    domain_label="Architecture",
                    display_title="Failed entry",
                    summary="Failure",
                ),
                _entry_row(
                    entry_id="queued-one",
                    pipeline_status="queued_for_transcription",
                    ingest_state="queued_for_transcription",
                    cognitive_status="unreviewed",
                    created_at=now - timedelta(days=4),
                    updated_at=now - timedelta(hours=10),
                    source_channel="watch_audio",
                    type_id="idea",
                    type_label="Idea",
                    domain_id="architecture",
                    domain_label="Architecture",
                    display_title="Queued",
                    summary="Queued summary",
                ),
            ],
        )
    service = DashboardSummaryService(engine=engine, default_time_window_days=5)
    summary = service.build_summary(time_window_days=5)

    assert summary["pipeline"]["total"] == 4
    assert summary["pipeline"]["by_ingest_state"]["processed"] == 1
    assert summary["cognitive"]["by_status"]["review_needed"] == 1
    failure_counts = summary["pipeline"]["failure_window"]["counts"]
    assert failure_counts["transcription_failed"] == 1

    needs_review = summary["cognitive"]["needs_review"]["items"]
    assert len(needs_review) == 1
    assert needs_review[0]["entry_id"] == "needs-review"
    assert needs_review[0]["display_title"] == "Needs attention"

    recent_processed = summary["recent"]["processed"]
    assert recent_processed and recent_processed[0]["entry_id"] == "processed-1"

    top_types = summary["taxonomy"]["top_types"]
    assert top_types[0]["id"] == "idea"
    assert summary["taxonomy"]["top_domains"][0]["label"] == "Architecture"

    assert len(summary["momentum"]["recent_intake"]) == 5
    assert summary["meta"]["time_window_days"] == 5
    assert summary["meta"]["failure_window_days"] == 7

    source_mix = summary["momentum"]["source_mix"]
    assert source_mix[0]["source_channel"] == "watch_audio"
    assert summary["meta"]["include_archived"] is False


def test_time_window_clamps_to_maximum():
    engine, entries, *_ = _setup_schema()
    now = datetime(2025, 12, 10, tzinfo=timezone.utc)
    with engine.begin() as conn:
        conn.execute(
            entries.insert(),
            [
                _entry_row(
                    entry_id="single",
                    pipeline_status="semantic_complete",
                    ingest_state="processed",
                    cognitive_status="complete",
                    created_at=now,
                    updated_at=now,
                    source_channel="watch_audio",
                    type_id=None,
                    type_label=None,
                    domain_id=None,
                    domain_label=None,
                )
            ],
        )
    service = DashboardSummaryService(engine=engine)
    summary = service.build_summary(time_window_days=MAX_TIME_WINDOW_DAYS + 15)
    assert summary["meta"]["time_window_days"] == MAX_TIME_WINDOW_DAYS
