"""Resilient model download orchestrator (007).

Replaces the single-connection `huggingface_hub.snapshot_download(...)` path with
a Python port of `download_aria.sh`: caffeinate keeps the Mac awake, curl pulls
the small metadata files, aria2c pulls the multi-GB safetensors shards with
parallel byte-range streams, indefinite retry, and `--continue=true` resume.

When `aria2c` is not on PATH, the installer auto-falls back to the existing
`snapshot_download(resume_download=True, token=…)` path with a single yellow
warning line (FR-019).

Contracts:
  - `specs/007-robust-model-download/contracts/downloader-cli-contract.md`
  - `specs/007-robust-model-download/contracts/token-resolution-contract.md`
  - `specs/007-robust-model-download/contracts/progress-bridge-contract.md`
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import time

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from speakloop.installer import aria
from speakloop.installer.aria import Aria2Outcome, Aria2Progress
from speakloop.installer.manifest import Model
from speakloop.installer.shards import discover_shards
from speakloop.installer.tokens import ResolvedToken, resolve_token

# --------------------------------------------------------------------------- #
# Pinned constants (contracts/downloader-cli-contract.md §8)                  #
# --------------------------------------------------------------------------- #

MAX_CONNECTIONS_PER_SERVER = 16
SPLIT = 16
MIN_SPLIT_SIZE = "1M"
ARIA2_INNER_RETRY_WAIT_SEC = 5
ARIA2_CONNECT_TIMEOUT_SEC = 30
PYTHON_OUTER_RETRY_WAIT_SEC = 10
CURL_RETRY_COUNT = 5
CURL_RETRY_DELAY_SEC = 3
# curl exit codes that mean a NETWORK-class failure (not an absent file): couldn't-resolve-host
# (6), failed-to-connect (7), operation-timeout (28), TLS/SSL connect error (35), failure
# receiving network data (56). Distinct from exit 22 (HTTP >= 400 under `-f` → file absent).
_CURL_NETWORK_EXITS: frozenset[int] = frozenset({6, 7, 28, 35, 56})

META_FILES: tuple[str, ...] = (
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
    "added_tokens.json",
    "generation_config.json",
    "chat_template.jinja",
    "model.safetensors.index.json",
    # 016: the wav2vec2 pronunciation model's feature-extractor config. Best-effort like
    # every META_FILE — repos without it skip it silently, so no existing model changes.
    "preprocessor_config.json",
    "README.md",
)

_HF_BASE = "https://huggingface.co"


# --------------------------------------------------------------------------- #
# Public entry point                                                          #
# --------------------------------------------------------------------------- #


def download_model(model: Model, *, console: Console | None = None) -> None:
    """Download every shard belonging to `model.hf_repo_id` into `model.local_path`.

    Public signature is preserved (007 plan §Project Structure); only the body
    changed. Raises one of the typed `InstallFailedError` subclasses on a hard
    failure; transient failures retry indefinitely.

    Note: caffeinate is spawned ONCE per install at `ensure_models(...)` entry
    (contract §2), not here — so a multi-model phase holds a single wakelock
    across all shards instead of toggling per model.
    """
    console = console or Console()
    model.local_path.mkdir(parents=True, exist_ok=True)
    console.print(f"Downloading [bold]{model.name}[/bold] → {model.local_path}")

    token = resolve_token()
    _maybe_announce_token_source(token, console)

    aria_bin = shutil.which("aria2c")
    if aria_bin is None:
        _fallback_snapshot_download(model, token=token, console=console)
        return
    _download_via_aria(model, aria_bin=aria_bin, token=token, console=console)


# --------------------------------------------------------------------------- #
# Token diagnostic                                                            #
# --------------------------------------------------------------------------- #


def _maybe_announce_token_source(token: ResolvedToken, console: Console) -> None:
    """Print exactly ONE line naming the active credential source (or nothing).

    Per `contracts/token-resolution-contract.md §5`. Never prints the token value.
    """
    if token.source == "env":
        console.print("Using HuggingFace token from $HF_TOKEN.")
    elif token.source == "hf_cli_file":
        console.print("Using HuggingFace token from ~/.cache/huggingface/token.")
    # anonymous → silence (default needs no announcement)


# --------------------------------------------------------------------------- #
# caffeinate (called from installer.ensure_models — contract §2)              #
# --------------------------------------------------------------------------- #


def spawn_caffeinate(console: Console) -> subprocess.Popen | None:
    """Spawn `caffeinate -dimsu -w <pid>`. Best-effort: missing caffeinate
    surfaces one yellow warning and we proceed without sleep prevention."""
    try:
        return subprocess.Popen(
            ["caffeinate", "-dimsu", "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        console.print(
            "[yellow]caffeinate not found — sleep prevention disabled.[/yellow]"
        )
        return None


def terminate_caffeinate(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    # Best-effort: caffeinate already exited because of the `-w <pid>` guard,
    # or the process object lost track. Either way, do not propagate.
    with contextlib.suppress(Exception):
        proc.terminate()


# --------------------------------------------------------------------------- #
# aria2 path                                                                  #
# --------------------------------------------------------------------------- #


def _download_via_aria(
    model: Model,
    *,
    aria_bin: str,
    token: ResolvedToken,
    console: Console,
) -> None:
    repo_id = model.hf_repo_id
    local_dir = model.local_path
    base_url = f"{_HF_BASE}/{repo_id}/resolve/main"

    _fetch_metadata(local_dir=local_dir, base_url=base_url, token=token, console=console)
    # 016: a model may declare its weight files explicitly (repos with no safetensors
    # index, where `discover_shards` would fall back to a non-existent model.safetensors).
    # None ⇒ today's behavior (discover safetensors shards), byte-identical for every
    # existing model.
    shards = list(model.weight_files) if model.weight_files else discover_shards(local_dir)
    console.print("[bold]==> Shards to download:[/bold]")
    for shard in shards:
        console.print(f"    {shard}")

    columns = (
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )
    with Progress(*columns, console=console, transient=False) as progress:
        for shard in shards:
            url = f"{base_url}/{shard}"
            cmd = [
                aria_bin,
                f"--max-connection-per-server={MAX_CONNECTIONS_PER_SERVER}",
                f"--split={SPLIT}",
                f"--min-split-size={MIN_SPLIT_SIZE}",
                "--continue=true",
                "--max-tries=0",
                f"--retry-wait={ARIA2_INNER_RETRY_WAIT_SEC}",
                f"--connect-timeout={ARIA2_CONNECT_TIMEOUT_SEC}",
                f"--out={shard}",
                f"--dir={local_dir}",
                url,
            ]
            if token.value is not None:
                cmd.insert(1, f"--header=Authorization: Bearer {token.value}")

            task_id = progress.add_task(f"{model.name} / {shard}", total=None)

            def _on_progress(snap: Aria2Progress, _tid=task_id) -> None:
                progress.update(
                    _tid,
                    total=snap.bytes_total,
                    completed=snap.bytes_received,
                )

            while True:
                outcome, err = aria.run(
                    cmd,
                    shard_filename=shard,
                    on_progress=_on_progress,
                )
                if outcome is Aria2Outcome.SUCCESS:
                    break
                if outcome is Aria2Outcome.HARD_FAILURE:
                    assert err is not None
                    progress.console.print(
                        f"[red bold]Download failed:[/red bold] {err}"
                    )
                    raise err
                # TRANSIENT — leave the task at its prior `completed` so the
                # bar appears to freeze, then resumes (FR-020).
                progress.console.print(
                    "[yellow]Connection lost — retrying in 10s…[/yellow]"
                )
                time.sleep(PYTHON_OUTER_RETRY_WAIT_SEC)


def _fetch_metadata(
    *,
    local_dir,
    base_url: str,
    token: ResolvedToken,
    console: Console,
) -> None:
    console.print("==> Downloading metadata files")
    for name in META_FILES:
        out_path = local_dir / name
        cmd = [
            "curl",
            "-L",
            "-f",
            "-s",
            "-o",
            str(out_path),
            "--retry",
            str(CURL_RETRY_COUNT),
            "--retry-delay",
            str(CURL_RETRY_DELAY_SEC),
            f"{base_url}/{name}",
        ]
        if token.value is not None:
            cmd[1:1] = ["-H", f"Authorization: Bearer {token.value}"]
        proc = subprocess.run(cmd)
        if proc.returncode == 0:
            console.print(f"    {name} ... ok")
        elif proc.returncode in _CURL_NETWORK_EXITS:
            # A network-class curl failure (DNS/connect/timeout/TLS/recv) AFTER curl's own
            # --retry attempts — NOT a missing file. Say so distinctly rather than the
            # "not in repo, skipping" absence message: a swallowed blip on
            # `model.safetensors.index.json` makes `discover_shards` fall back to a single
            # `model.safetensors` that then 404s as "repo or shard filename is wrong", a
            # misdiagnosis of a transient network error (IMP-028).
            if out_path.exists():
                with contextlib.suppress(OSError):
                    out_path.unlink()
            console.print(
                f"    [yellow]{name} ... network error (curl exit {proc.returncode}); the "
                "shard plan may be incomplete — check your connection and re-run.[/yellow]"
            )
        else:
            # Many HF repos omit some META_FILES; a plain HTTP 404 (curl exit 22) is not an error.
            if out_path.exists():
                with contextlib.suppress(OSError):
                    out_path.unlink()
            console.print(f"    {name} ... (not in repo, skipping)")


# --------------------------------------------------------------------------- #
# Fallback path (FR-019)                                                      #
# --------------------------------------------------------------------------- #


def _fallback_snapshot_download(
    model: Model,
    *,
    token: ResolvedToken,
    console: Console,
) -> None:
    from huggingface_hub import snapshot_download

    console.print(
        "[yellow]aria2 not found — using single-connection fallback. "
        "Install with: brew install aria2[/yellow]"
    )
    snapshot_download(
        repo_id=model.hf_repo_id,
        local_dir=str(model.local_path),
        resume_download=True,
        token=token.value,
    )
