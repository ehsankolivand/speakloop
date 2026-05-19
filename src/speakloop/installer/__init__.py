"""Installer orchestrator: compute missing → consent → download → re-validate."""

from __future__ import annotations

from rich.console import Console

from speakloop.installer import consent as _consent
from speakloop.installer import downloader, manifest, validator


class InstallDeclinedError(Exception):
    """Raised when the user declines the download consent prompt."""


class InstallFailedError(Exception):
    """Raised when validation fails after a download."""


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

    console.print(f"[bold]Phase {phase}[/bold]: {len(missing)} model(s) need to be downloaded.")

    consented = consent_fn(missing, console=console, input_fn=input_fn)
    if not consented:
        raise InstallDeclinedError("User declined model download.")

    for m in missing:
        download_fn(m, console=console)

    still_bad = _missing_or_invalid(required)
    if still_bad:
        names = ", ".join(m.name for m in still_bad)
        raise InstallFailedError(f"Validation failed after download: {names}")


__all__ = [
    "InstallDeclinedError",
    "InstallFailedError",
    "ensure_models",
    "manifest",
]
