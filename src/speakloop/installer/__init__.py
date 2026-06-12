"""Installer orchestrator: compute missing → consent → download → re-validate."""

from __future__ import annotations

import atexit

from rich.console import Console


class InstallDeclinedError(Exception):
    """Raised when the user declines the download consent prompt."""


class InstallFailedError(Exception):
    """Raised when validation fails after a download."""


class DownloadAuthError(InstallFailedError):
    """Raised on a 401/403 from the HuggingFace endpoint (007)."""


class DownloadNotFoundError(InstallFailedError):
    """Raised on a 404 from the HuggingFace endpoint (007)."""


class DownloadDiskError(InstallFailedError):
    """Raised on a disk-full / write error during the download (007)."""


class ShardDiscoveryError(InstallFailedError):
    """Raised on a malformed `model.safetensors.index.json` (007)."""


# Imports must follow the exception definitions: `aria.py` and `downloader.py`
# import these typed errors back from the package root, so they must already be
# bound when those submodules execute.
from speakloop.installer import consent as _consent  # noqa: E402
from speakloop.installer import downloader, manifest, validator  # noqa: E402


def engine_needs_local_llm(engine: str, *, listen_only: bool) -> bool:
    """Whether a run needs the large local feedback LLM (Phase C / Qwen) downloaded (015).

    Only the ``local`` engine on a full (non-listen-only) session needs it; the cloud
    engines (``openrouter``, ``claude``) never do, and listen-only needs neither ASR nor
    the LLM. The single source of truth for engine-aware provisioning — used by
    ``cli.practice``, ``cli.setup``, and (indirectly) ``cli.doctor``.
    """
    return engine == "local" and not listen_only


def _missing_or_invalid(models: list[manifest.Model]) -> list[manifest.Model]:
    return [m for m in models if not validator.validate(m).ok]


def ensure_models(
    phase: manifest.Phase,
    *,
    console: Console | None = None,
    consent_fn=_consent.prompt_for_consent,
    download_fn=downloader.download_model,
    input_fn=input,
) -> None:
    """Ensure every model required for `phase` is present and valid.

    Raises InstallDeclinedError if the user declines; InstallFailedError if
    validation still fails after a download attempt.
    """
    console = console or Console()
    required = manifest.models_for_phase(phase)
    missing = _missing_or_invalid(required)
    if not missing:
        return

    # 007 contract §2: ONE caffeinate per install, spawned BEFORE the consent
    # prompt so the wakelock covers consent + metadata + all shard downloads.
    # try/finally + atexit are paired (atexit is defense in depth against a
    # hard interpreter exit that skips try/finally).
    caffeinate_proc = downloader.spawn_caffeinate(console)
    atexit_handler = lambda: downloader.terminate_caffeinate(caffeinate_proc)  # noqa: E731
    atexit.register(atexit_handler)
    try:
        console.print(
            f"[bold]Phase {phase}[/bold]: {len(missing)} model(s) need to be downloaded."
        )

        consented = consent_fn(missing, console=console, input_fn=input_fn)
        if not consented:
            raise InstallDeclinedError("User declined model download.")

        for m in missing:
            download_fn(m, console=console)

        still_bad = _missing_or_invalid(required)
        if still_bad:
            names = ", ".join(m.name for m in still_bad)
            raise InstallFailedError(f"Validation failed after download: {names}")
    finally:
        downloader.terminate_caffeinate(caffeinate_proc)
        atexit.unregister(atexit_handler)


__all__ = [
    "DownloadAuthError",
    "DownloadDiskError",
    "DownloadNotFoundError",
    "InstallDeclinedError",
    "InstallFailedError",
    "ShardDiscoveryError",
    "engine_needs_local_llm",
    "ensure_models",
    "manifest",
]
