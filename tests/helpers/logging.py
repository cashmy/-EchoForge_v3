"""Test helpers for capturing structured logging output."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


class RecordingLogger:
    """Minimal logger stub that records structured log calls."""

    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []

    def _record(self, level: str, message: str, *args: Any, **kwargs: Any) -> None:
        self.records.append(
            {
                "level": level,
                "message": message,
                "args": args,
                "kwargs": kwargs,
                "extra": dict(kwargs.get("extra") or {}),
            }
        )

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._record("debug", message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._record("info", message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._record("warning", message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._record("error", message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._record("exception", message, *args, **kwargs)


def find_log(
    records: List[Dict[str, Any]], *, level: str, message: str
) -> Dict[str, Any]:
    for record in records:
        if record["level"] == level and record["message"] == message:
            return record
    raise AssertionError(f"Log '{message}' at level '{level}' not recorded")


def assert_extra_contains(record: Dict[str, Any], **expected: Any) -> None:
    extra = record.get("extra") or {}
    for key, value in expected.items():
        assert extra.get(key) == value, (
            f"Expected extra['{key}'] == {value!r}, found {extra.get(key)!r}"
        )


def assert_extra_has_keys(record: Dict[str, Any], keys: Iterable[str]) -> None:
    extra = record.get("extra") or {}
    missing = [key for key in keys if key not in extra]
    assert not missing, f"Missing keys in log extra: {missing}"
