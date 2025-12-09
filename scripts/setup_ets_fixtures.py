"""Utility to generate deterministic ETS fixtures and optionally copy them into watch roots."""

from __future__ import annotations

import argparse
import json
import math
import struct
import wave
from pathlib import Path
from typing import Iterable, Tuple

AUDIO_FIXTURES: Tuple[Tuple[str, float, float], ...] = (
    ("20250907115516.wav", 440.0, 1.5),
    ("20250908132309.wav", 554.37, 1.2),
)

DOCUMENT_FIXTURES = {
    "doc_pipeline_reference.txt": """# EchoForge Audio Transcript (Reference)

This file validates the EF-03 extraction worker when text-based documents are queued.
It contains multiple paragraphs, markdown headers, and list items so normalization can collapse
whitespace properly.

- Bullet one with   extra   spaces
- Bullet two referencing INF-03 logging

Timestamp 00:01 Hello world!
""",
    "doc_ocr_simulation.txt": """SCANNED_PAGE_001 OCR REQUIRED
This second document emulates an OCR-heavy ingestion by including uppercase text and spacing artifacts.
Paragraphs should still be segmented even if speaker labels exist.
SPEAKER 1: THIS IS A TEST.
SPEAKER 2: Another TEST case.
""",
}

NORMALIZED_SNAPSHOT = {
    "entry_id": "00000000-0000-0000-0000-etsrefnorm",
    "source": "transcription",
    "normalized_text": "Hello world! This is a test entry for ETS dry runs.",
    "segment_count": 1,
    "chunk_count": 1,
    "profile": "standard",
    "pipeline_status": "normalization_complete",
    "correlation_id": "ets-norm-ref-001",
}

FIXTURE_ROOT = Path("tests/fixtures/ets_pipeline")


def _write_sine_wave(
    path: Path, freq: float, duration: float, sample_rate: int = 16000
) -> None:
    n_samples = int(sample_rate * duration)
    frames = bytearray()
    for index in range(n_samples):
        value = int(32767 * math.sin(2 * math.pi * freq * index / sample_rate))
        frames += struct.pack("<h", value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)


def _write_documents(root: Path) -> None:
    for filename, contents in DOCUMENT_FIXTURES.items():
        target = root / "documents" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents.strip() + "\n", encoding="utf-8")


def _write_audio(root: Path) -> None:
    audio_dir = root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for filename, freq, duration in AUDIO_FIXTURES:
        _write_sine_wave(audio_dir / filename, freq=freq, duration=duration)


def _write_payload(root: Path) -> None:
    payload_dir = root / "payloads"
    payload_dir.mkdir(parents=True, exist_ok=True)
    target = payload_dir / "normalized_snapshot.json"
    target.write_text(json.dumps(NORMALIZED_SNAPSHOT, indent=2), encoding="utf-8")


def _copy_fixture(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())


def copy_to_watch_roots(base_watch_root: Path, fixture_root: Path) -> None:
    audio_pairs: Iterable[Tuple[str, Path]] = (
        ("audio", fixture_root / "audio" / filename) for filename, *_ in AUDIO_FIXTURES
    )
    for subdir, src in audio_pairs:
        dest = base_watch_root / subdir / "incoming" / src.name
        _copy_fixture(src, dest)

    document_pairs = (
        ("documents", fixture_root / "documents" / filename)
        for filename in DOCUMENT_FIXTURES
    )
    for subdir, src in document_pairs:
        dest = base_watch_root / subdir / "incoming" / src.name
        _copy_fixture(src, dest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--copy-to-watch-roots",
        action="store_true",
        help="Copy fixtures into watch_roots/<channel>/incoming after generating them.",
    )
    parser.add_argument(
        "--watch-root-base",
        default="watch_roots",
        help="Root path containing audio/doc watch directories (defaults to ./watch_roots).",
    )
    args = parser.parse_args()

    _write_audio(FIXTURE_ROOT)
    _write_documents(FIXTURE_ROOT)
    _write_payload(FIXTURE_ROOT)

    if args.copy_to_watch_roots:
        base_watch = Path(args.watch_root_base)
        if not base_watch.exists():
            parser.error(
                f"watch root '{base_watch}' not found. Run 'python scripts/setup_watch_roots.py' first "
                "or pass --watch-root-base with the correct path."
            )
        copy_to_watch_roots(base_watch, FIXTURE_ROOT)
        print(
            f"Copied fixtures ({len(AUDIO_FIXTURES)} audio, {len(DOCUMENT_FIXTURES)} doc) into "
            f"{base_watch}\n"
        )
    else:
        print(
            "Generated ETS fixtures under tests/fixtures/ets_pipeline. "
            "Re-run with --copy-to-watch-roots after initializing watch roots to stage them for a dry run."
        )


if __name__ == "__main__":
    main()
