"""Utilities for EF-01 watch folder scaffolding.

EF-01 requires each configured watch root to expose a predictable layout:

```
<watch_root>/
  incoming/
  processing/
  processed/
  failed/
```

This module centralizes the logic that ensures those directories exist. Keeping
it here allows future watcher implementations (polling APIs, filesystem events,
etc.) to import a single helper before they start monitoring the folders.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

__all__ = [
    "WATCH_SUBDIRECTORIES",
    "ensure_watch_root_layout",
    "ensure_watch_roots_layout",
    "list_incoming_paths",
]

# Order matters for deterministic test assertions and future logging.
WATCH_SUBDIRECTORIES: Sequence[str] = ("incoming", "processing", "processed", "failed")


def ensure_watch_root_layout(watch_root: str | Path) -> Path:
    """Create the expected EF-01 subdirectories for a single watch root."""

    root_path = Path(watch_root).expanduser()
    root_path.mkdir(parents=True, exist_ok=True)
    for subdir in WATCH_SUBDIRECTORIES:
        (root_path / subdir).mkdir(parents=True, exist_ok=True)
    return root_path


def ensure_watch_roots_layout(watch_roots: Iterable[str | Path]) -> List[Path]:
    """Ensure all configured watch roots contain the EF-01 folder hierarchy."""

    normalized_roots: List[Path] = []
    for root in watch_roots:
        normalized_roots.append(ensure_watch_root_layout(root))
    return normalized_roots


def list_incoming_paths(watch_roots: Iterable[str | Path]) -> List[Path]:
    """Return absolute paths to each `incoming/` folder for watcher registration."""

    return [Path(root).expanduser() / WATCH_SUBDIRECTORIES[0] for root in watch_roots]
