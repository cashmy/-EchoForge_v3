from http import HTTPStatus
from typing import Any

import pytest

from backend.app.domain.taxonomy import (
    InMemoryTaxonomyRepository,
    TaxonomyKind,
    TaxonomyService,
    TaxonomyServiceError,
)
from backend.app.infra.events import EventEmitter
from backend.app.infra.metrics import MetricsClient


class StubEmitter(EventEmitter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def emit(self, topic: str, payload: dict[str, Any]) -> None:
        self.calls.append((topic, payload))


class StubMetrics(MetricsClient):
    def __init__(self) -> None:
        self.increments: list[tuple[str, int]] = []
        self.gauges: list[tuple[str, int]] = []

    def increment(self, metric: str, value: int = 1) -> None:
        self.increments.append((metric, value))

    def gauge(self, metric: str, value: int) -> None:
        self.gauges.append((metric, value))


def test_create_rejects_duplicate_name_case_insensitive() -> None:
    repo = InMemoryTaxonomyRepository()
    service = TaxonomyService(repository=repo)

    service.create(
        TaxonomyKind.TYPE,
        {
            "id": "book_idea",
            "name": "BookIdea",
            "label": "Book Idea",
        },
    )

    with pytest.raises(TaxonomyServiceError) as exc:
        service.create(
            TaxonomyKind.TYPE,
            {
                "id": "book_idea_v2",
                "name": "bookidea",  # same name different casing
                "label": "Book Idea 2",
            },
        )

    assert exc.value.status_code == HTTPStatus.CONFLICT
    assert exc.value.error_code == "EF07-CONFLICT"


def test_update_rejects_duplicate_name() -> None:
    repo = InMemoryTaxonomyRepository()
    service = TaxonomyService(repository=repo)
    service.create(
        TaxonomyKind.TYPE,
        {"id": "book", "label": "Book", "name": "Book"},
    )
    service.create(
        TaxonomyKind.TYPE,
        {"id": "note", "label": "Note", "name": "Note"},
    )

    with pytest.raises(TaxonomyServiceError) as exc:
        service.update(
            TaxonomyKind.TYPE,
            taxonomy_id="note",
            payload={"name": "book"},
        )

    assert exc.value.status_code == HTTPStatus.CONFLICT
    assert exc.value.details == {"name": "book"}


def test_sort_order_validation() -> None:
    service = TaxonomyService(repository=InMemoryTaxonomyRepository())

    with pytest.raises(TaxonomyServiceError) as exc:
        service.create(
            TaxonomyKind.TYPE,
            {
                "id": "invalid_sort",
                "label": "Invalid",
                "sort_order": 20_001,
            },
        )

    assert exc.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc.value.details == {"field": "sort_order"}


def test_hard_delete_gate_blocks_when_disabled() -> None:
    service = TaxonomyService(
        allow_hard_delete=False,
        repository=InMemoryTaxonomyRepository(),
    )
    service.create(
        TaxonomyKind.TYPE,
        {"id": "book", "label": "Book"},
    )

    with pytest.raises(TaxonomyServiceError) as exc:
        service.delete(TaxonomyKind.TYPE, taxonomy_id="book")

    assert exc.value.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert exc.value.details == {"reason": "hard_delete_disabled"}


def test_delete_returns_reference_metadata() -> None:
    repo = InMemoryTaxonomyRepository()
    service = TaxonomyService(allow_hard_delete=True, repository=repo)
    service.create(
        TaxonomyKind.TYPE,
        {"id": "book", "label": "Book"},
    )
    repo._store[TaxonomyKind.TYPE]["book"].referenced_entries = 3  # test shim
    deleted = service.delete(TaxonomyKind.TYPE, taxonomy_id="book")

    assert deleted.referenced_entries == 3


def test_create_emits_event_and_metrics() -> None:
    repo = InMemoryTaxonomyRepository()
    emitter = StubEmitter()
    metrics = StubMetrics()
    service = TaxonomyService(
        allow_hard_delete=True,
        repository=repo,
        event_emitter=emitter,
        metrics=metrics,
    )

    service.create(
        TaxonomyKind.TYPE,
        {"id": "book", "label": "Book"},
    )

    assert emitter.calls
    topic, payload = emitter.calls[-1]
    assert topic == "taxonomy.type.created"
    assert payload["changes"]["after"]["label"] == "Book"
    assert ("taxonomy_type_created_total", 1) in metrics.increments
    assert metrics.gauges[-1] == ("taxonomy_type_active_total", 1)


def test_update_toggle_emits_deactivation_event() -> None:
    repo = InMemoryTaxonomyRepository()
    emitter = StubEmitter()
    metrics = StubMetrics()
    service = TaxonomyService(
        allow_hard_delete=True,
        repository=repo,
        event_emitter=emitter,
        metrics=metrics,
    )
    service.create(
        TaxonomyKind.TYPE,
        {"id": "book", "label": "Book"},
    )
    emitter.calls.clear()
    metrics.increments.clear()
    metrics.gauges.clear()

    service.update(
        TaxonomyKind.TYPE,
        taxonomy_id="book",
        payload={"active": False},
    )

    assert emitter.calls
    topic, payload = emitter.calls[-1]
    assert topic == "taxonomy.type.deactivated"
    assert payload["changes"]["delta"]["active"] == {"before": True, "after": False}
    assert metrics.increments[-1][0] == "taxonomy_type_deactivated_total"
    assert metrics.gauges[-1] == ("taxonomy_type_active_total", 0)


def test_delete_block_records_metric() -> None:
    repo = InMemoryTaxonomyRepository()
    emitter = StubEmitter()
    metrics = StubMetrics()
    service = TaxonomyService(
        allow_hard_delete=False,
        repository=repo,
        event_emitter=emitter,
        metrics=metrics,
    )
    service.create(
        TaxonomyKind.TYPE,
        {"id": "book", "label": "Book"},
    )
    emitter.calls.clear()
    metrics.increments.clear()

    with pytest.raises(TaxonomyServiceError):
        service.delete(TaxonomyKind.TYPE, taxonomy_id="book")

    assert ("taxonomy_delete_blocked_total", 1) in metrics.increments
    assert emitter.calls == []
