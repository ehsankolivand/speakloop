"""`speakloop rebuild` — rebuild the derived store from session files (010, P2a).

Read-only over session reports; loads NO engines (Principle VIII). Proves the
store is fully rebuildable from `data/sessions/*.md` (research R4).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console

from speakloop.config import paths
from speakloop.store import io as store_io
from speakloop.store import rebuild as store_rebuild


def run(sessions_dir: Path | None = None) -> None:
    console = Console()
    src = Path(sessions_dir) if sessions_dir else paths.sessions_dir()
    if not src.exists():
        console.print(f"[yellow]No sessions directory at {src} — nothing to rebuild.[/yellow]")
        return

    store = store_rebuild.rebuild(src, rebuilt_at=datetime.now().isoformat(timespec="seconds"))
    dest = paths.store_path()
    store_io.save_atomic(dest, store)

    console.print(f"[green]Rebuilt store[/green] → {dest}")
    console.print(
        f"  questions scheduled: {len(store.schedule)}\n"
        f"  key-point sets:      {sum(len(v) for v in store.key_points.values())}\n"
        f"  grammar patterns:    {len(store.patterns)}"
    )
