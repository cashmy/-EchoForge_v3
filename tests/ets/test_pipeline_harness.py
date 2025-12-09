"""ETS marker tests that exercise EF-02 → EF-05 end-to-end."""

from __future__ import annotations

import pytest

from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.jobs import semantic_worker
from tests.helpers.logging import assert_extra_contains, find_log
from tests.helpers.pipeline_harness import FailingSemanticClient, PipelineHarness

pytestmark = [
    pytest.mark.ets_pipeline,
    pytest.mark.ef02,
    pytest.mark.ef03,
    pytest.mark.ef04,
    pytest.mark.ef05,
]


def test_audio_pipeline_happy_path_emits_expected_logs(monkeypatch, tmp_path) -> None:
    harness = PipelineHarness(tmp_path, patcher=monkeypatch)

    entry_id = harness.run_audio_pipeline(correlation_id="ets-audio-success")
    snapshot = harness.gateway.get_entry(entry_id)

    assert snapshot.pipeline_status == PIPELINE_STATUS.SEMANTIC_COMPLETE
    assert snapshot.summary is not None

    expected_logs = [
        ("transcription_started", "info"),
        ("transcription_completed", "info"),
        ("normalization_started", "info"),
        ("normalization_completed", "info"),
        ("semantic_job_started", "info"),
        ("semantic_job_completed", "info"),
    ]
    for message, level in expected_logs:
        record = find_log(harness.logger.records, message=message, level=level)
        assert record is not None


def test_document_pipeline_happy_path_includes_extraction_logs(
    monkeypatch, tmp_path
) -> None:
    harness = PipelineHarness(tmp_path, patcher=monkeypatch)

    entry_id = harness.run_document_pipeline(correlation_id="ets-doc-success")
    snapshot = harness.gateway.get_entry(entry_id)

    assert snapshot.pipeline_status == PIPELINE_STATUS.SEMANTIC_COMPLETE
    extraction_started = find_log(
        harness.logger.records,
        message="extraction_started",
        level="info",
    )
    assert_extra_contains(
        extraction_started,
        stage="extraction",
        pipeline_status=PIPELINE_STATUS.EXTRACTION_IN_PROGRESS,
    )
    extraction_completed = find_log(
        harness.logger.records,
        message="extraction_completed",
        level="info",
    )
    assert_extra_contains(
        extraction_completed,
        pipeline_status=PIPELINE_STATUS.EXTRACTION_COMPLETE,
    )


def test_audio_pipeline_semantic_failure_records_pipeline_failure(
    monkeypatch, tmp_path
) -> None:
    harness = PipelineHarness(tmp_path, patcher=monkeypatch)
    failing_client = FailingSemanticClient()

    with pytest.raises(semantic_worker.SemanticWorkerError):
        harness.run_audio_pipeline(
            correlation_id="ets-semantic-failure",
            semantic_client=failing_client,
        )

    entry_id = harness.last_entry_id
    assert entry_id is not None
    snapshot = harness.gateway.get_entry(entry_id)
    assert snapshot.pipeline_status == PIPELINE_STATUS.SEMANTIC_FAILED

    failure_log = find_log(
        harness.logger.records,
        message="semantic_job_failed",
        level="error",
    )
    assert_extra_contains(
        failure_log,
        stage="semantics",
        pipeline_status=PIPELINE_STATUS.SEMANTIC_FAILED,
        error_code="provider_unavailable",
    )
    started_log = find_log(
        harness.logger.records,
        message="semantic_job_started",
        level="info",
    )
    assert_extra_contains(
        started_log,
        pipeline_status=PIPELINE_STATUS.SEMANTIC_IN_PROGRESS,
    )
