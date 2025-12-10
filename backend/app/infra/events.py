"""INF-03 capture event helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

from .logging import get_logger

logger = get_logger(__name__)


class EventEmitter(Protocol):  # pragma: no cover - interface only
    """Abstract capture-event publisher."""

    def emit(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publish an event to INF-03."""


@dataclass
class LoggingEventEmitter(EventEmitter):
    """Default emitter that logs payloads (placeholder until INF-03 wires in)."""

    topic_prefix: str = "inf03"

    def emit(self, topic: str, payload: Dict[str, Any]) -> None:
        logger.info(
            "capture_event",
            extra={
                "topic": f"{self.topic_prefix}.{topic}",
                "payload": payload,
            },
        )


_singleton: LoggingEventEmitter | None = None


def get_event_emitter() -> EventEmitter:
    """Return the process-wide capture-event emitter."""

    global _singleton
    if _singleton is None:
        _singleton = LoggingEventEmitter()
    return _singleton
