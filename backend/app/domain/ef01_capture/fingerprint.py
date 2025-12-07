"""Fingerprint utilities for EF-01 capture flows.

M01-T04 requires EF-01 to compute a stable fingerprint for watched files so we
can enforce idempotency when scanning `incoming/` directories. This helper keeps
that logic centralized and can later be extended to support alternate
strategies.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Tuple

DEFAULT_FILE_FINGERPRINT_ALGO = "sha256(name|size|mtime_ns)"


def compute_file_fingerprint(path: str | Path) -> Tuple[str, str]:
    """Return `(fingerprint, algorithm)` for the given file path."""

    resolved = Path(path)
    stat_result = resolved.stat()
    payload = f"{resolved.name}:{stat_result.st_size}:{stat_result.st_mtime_ns}".encode(
        "utf-8"
    )
    digest = hashlib.sha256(payload).hexdigest()
    return digest, DEFAULT_FILE_FINGERPRINT_ALGO
