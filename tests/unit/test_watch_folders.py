"""Unit tests for EF-01 watch folder helper utilities."""

# Coverage: EF-01

from pathlib import Path

import pytest

from backend.app.domain.ef01_capture.watch_folders import (
    WATCH_SUBDIRECTORIES,
    ensure_watch_root_layout,
    ensure_watch_roots_layout,
    list_incoming_paths,
)

pytestmark = [pytest.mark.ef01]


def test_ensure_watch_root_layout_creates_expected_structure(tmp_path):
    root = tmp_path / "audio"

    result = ensure_watch_root_layout(root)

    assert result == root
    assert root.exists()
    assert all((root / subdir).is_dir() for subdir in WATCH_SUBDIRECTORIES)


def test_ensure_watch_roots_layout_handles_existing_directories(tmp_path):
    root_one = tmp_path / "audio"
    root_two = tmp_path / "documents"
    # Pre-create a subset to ensure the helper handles partially populated roots.
    (root_two / "incoming").mkdir(parents=True, exist_ok=True)

    created = ensure_watch_roots_layout([root_one, root_two])

    assert created == [root_one, root_two]
    for root in created:
        for subdir in WATCH_SUBDIRECTORIES:
            assert (root / subdir).is_dir()


def test_list_incoming_paths_points_to_subdirectories(tmp_path):
    roots = [tmp_path / "audio", tmp_path / "documents"]
    ensure_watch_roots_layout(roots)

    incoming_paths = list_incoming_paths(roots)

    assert incoming_paths == [Path(root) / "incoming" for root in roots]
