"""Simple metrics facade until INF-03 counters are wired."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict

from .logging import get_logger

logger = get_logger(__name__)


class MetricsClient:  # pragma: no cover - simple helper
    """Basic counter/gauge interface."""

    def increment(self, metric: str, value: int = 1) -> None:
        raise NotImplementedError

    def gauge(self, metric: str, value: int) -> None:
        raise NotImplementedError


@dataclass
class InMemoryMetricsClient(MetricsClient):
    """Metrics sink used in dev/test builds."""

    counters: DefaultDict[str, int] = field(default_factory=lambda: defaultdict(int))
    gauges: DefaultDict[str, int] = field(default_factory=lambda: defaultdict(int))

    def increment(self, metric: str, value: int = 1) -> None:
        self.counters[metric] += value
        logger.info("metrics_increment", extra={"metric": metric, "value": value})

    def gauge(self, metric: str, value: int) -> None:
        self.gauges[metric] = value
        logger.info("metrics_gauge", extra={"metric": metric, "value": value})


_metrics_singleton: InMemoryMetricsClient | None = None


def get_metrics_client() -> MetricsClient:
    """Return the shared metrics client."""

    global _metrics_singleton
    if _metrics_singleton is None:
        _metrics_singleton = InMemoryMetricsClient()
    return _metrics_singleton
