"""Resumable model download via huggingface_hub.snapshot_download (FR-021)."""

from __future__ import annotations

from rich.console import Console

from speakloop.installer.manifest import Model


def download_model(model: Model, *, console: Console | None = None) -> None:
    """Download a model with byte-range resume.

    On Ctrl+C, partial files remain under `model.local_path` and a re-run
    of this function resumes from where it stopped (Constitution Principle VI;
    SC-002 ≤ 1 % re-fetch).
    """
    from huggingface_hub import snapshot_download

    console = console or Console()
    model.local_path.parent.mkdir(parents=True, exist_ok=True)
    console.print(f"Downloading [bold]{model.name}[/bold] → {model.local_path}")
    snapshot_download(
        repo_id=model.hf_repo_id,
        local_dir=str(model.local_path),
        resume_download=True,
    )
