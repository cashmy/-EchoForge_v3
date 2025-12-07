"""Utility script to scaffold local watch root directories for EF-01."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

WATCH_ROOT = Path("watch_roots")
SOURCE_DIRS = {
    "audio": ("incoming", "processing", "processed", "failed"),
    "documents": ("incoming", "processing", "processed", "failed"),
}
EXTRA_DIRS = (
    WATCH_ROOT / "transcripts",
    WATCH_ROOT / "tmp",
)


def ensure_dirs(base: Path = WATCH_ROOT) -> list[Path]:
    """Create the default watch root tree if missing and return touched paths."""

    created: list[Path] = []
    base.mkdir(parents=True, exist_ok=True)
    for source, subdirs in SOURCE_DIRS.items():
        root = base / source
        root.mkdir(parents=True, exist_ok=True)
        for subdir in subdirs:
            target = root / subdir
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                created.append(target)
    for path in EXTRA_DIRS:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
    return created


def main() -> None:
    created = ensure_dirs()
    if created:
        print("Created watch root directories:")
        for path in created:
            print(f" - {path}")
    else:
        print("watch_roots structure already exists; nothing to do.")


if __name__ == "__main__":
    main()
