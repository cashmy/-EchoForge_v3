"""Tests for EF-01 fingerprint helpers."""

import time

from backend.app.domain.ef01_capture.fingerprint import (
    DEFAULT_FILE_FINGERPRINT_ALGO,
    compute_file_fingerprint,
)


def test_compute_file_fingerprint_is_deterministic(tmp_path):
    target = tmp_path / "audio.wav"
    target.write_bytes(b"hello")

    fp_one, algo_one = compute_file_fingerprint(target)
    fp_two, algo_two = compute_file_fingerprint(target)

    assert fp_one == fp_two
    assert algo_one == algo_two == DEFAULT_FILE_FINGERPRINT_ALGO


def test_compute_file_fingerprint_changes_with_metadata(tmp_path):
    target = tmp_path / "audio.wav"
    target.write_bytes(b"hello")
    first_fp, _ = compute_file_fingerprint(target)

    # Wait briefly to guarantee mtime ticks forward on all supported filesystems.
    time.sleep(0.01)
    target.write_bytes(b"hello world")

    second_fp, _ = compute_file_fingerprint(target)

    assert first_fp != second_fp
