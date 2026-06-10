"""Derived-store JSON persistence (010-interview-loop, P2a).

stdlib ``json`` only. Atomic write (temp file + ``os.replace``), mirroring
``feedback.markdown_writer.write_atomic``. A missing / corrupt / older-version
file loads as an empty ``Store`` so callers can rebuild — the store is a cache,
never a source of truth (research R4).
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from speakloop.store.model import STORE_VERSION, Store


def load(path: Path) -> Store:
    """Load the store, or an empty one if missing/corrupt/too-new to read."""
    path = Path(path)
    if not path.exists():
        return Store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return Store()  # corrupt → rebuildable, so just start fresh
    store = Store.from_dict(data)
    if store.store_version > STORE_VERSION:
        # a newer on-disk schema we don't understand → treat as empty + rebuild
        return Store()
    return store


def save_atomic(path: Path, store: Store) -> None:
    """Write the store atomically (temp file in the same dir + ``os.replace``)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(store.to_dict(), indent=2, ensure_ascii=False, sort_keys=False)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
