"""Execute a single EF-01 watch-folder scan."""

from backend.app.config import load_settings
from backend.app.domain.ef01_capture.runtime import run_watch_once
from backend.app.domain.ef06_entrystore.gateway import build_entry_store_gateway


if __name__ == "__main__":
    settings = load_settings()
    gateway = build_entry_store_gateway()
    run_watch_once(settings.watch_roots, entry_gateway=gateway)
