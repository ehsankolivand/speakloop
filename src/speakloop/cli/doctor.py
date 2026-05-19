"""`speakloop doctor` — health-check (FR-024..FR-026)."""

from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import asdict, dataclass

import typer
from rich.console import Console
from rich.table import Table

from speakloop.audio import devices
from speakloop.config import paths
from speakloop.installer import manifest, validator


@dataclass
class CheckRow:
    section: str
    label: str
    status: str  # "OK" | "WARN" | "FAIL"
    detail: str = ""
    remediation: str = ""


def _python_runtime() -> CheckRow:
    ver = sys.version.split()[0]
    ok = sys.version_info[:2] == (3, 12)
    return CheckRow(
        section="Python",
        label=f"version {ver}",
        status="OK" if ok else "WARN",
        detail=f"executable: {sys.executable}",
        remediation="Install Python 3.12 (`brew install python@3.12`)." if not ok else "",
    )


def _models() -> list[CheckRow]:
    rows: list[CheckRow] = []
    for m in manifest.PHASE_C_MODELS:
        r = validator.validate(m)
        rows.append(
            CheckRow(
                section="Models",
                label=m.name,
                status="OK" if r.ok else "FAIL",
                detail=f"path: {m.local_path} (expected {r.expected_bytes:,} B)",
                remediation=(
                    "" if r.ok else "Run `speakloop practice` to consent and download this model."
                ),
            )
        )
    return rows


def _audio_devices() -> list[CheckRow]:
    out_info = devices.default_output()
    in_info = devices.default_input()
    out_row = CheckRow(
        section="Audio",
        label="output device",
        status="OK" if out_info else "FAIL",
        detail=f"{out_info.name} @ {out_info.default_samplerate:g} Hz" if out_info else "(none)",
        remediation="Plug in speakers/headphones and check System Settings → Sound."
        if not out_info
        else "",
    )
    in_row = CheckRow(
        section="Audio",
        label="input device",
        status="OK" if in_info else "WARN",
        detail=f"{in_info.name} @ {in_info.default_samplerate:g} Hz"
        if in_info
        else "(none — required for Phase B+)",
        remediation="Grant microphone permission in System Settings → Privacy → Microphone."
        if not in_info
        else "",
    )
    return [out_row, in_row]


def _sessions_dir() -> CheckRow:
    sd = paths.sessions_dir()
    sd.mkdir(parents=True, exist_ok=True)
    writable = os.access(sd, os.W_OK)
    return CheckRow(
        section="Filesystem",
        label=f"sessions_dir: {sd}",
        status="OK" if writable else "FAIL",
        detail="writable" if writable else "read-only",
        remediation=(
            "" if writable else f"chmod u+w {sd} or move data/sessions to a writable path."
        ),
    )


def _collect() -> list[CheckRow]:
    return [_python_runtime(), *_models(), *_audio_devices(), _sessions_dir()]


def _any_fail(rows: list[CheckRow]) -> bool:
    return any(r.status == "FAIL" for r in rows)


def _render_rich(rows: list[CheckRow], console: Console) -> None:
    table = Table(title=f"speakloop doctor — {platform.system()} {platform.machine()}")
    table.add_column("Section")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_column("Remediation")
    for r in rows:
        color = {"OK": "green", "WARN": "yellow", "FAIL": "red"}[r.status]
        table.add_row(
            r.section,
            r.label,
            f"[{color}]{r.status}[/{color}]",
            r.detail,
            r.remediation,
        )
    console.print(table)


def run(*, as_json: bool = False) -> None:
    """Entry point for `speakloop doctor`."""
    rows = _collect()
    if as_json:
        print(json.dumps([asdict(r) for r in rows], indent=2))
    else:
        # Print one human-friendly line per check (no truncation) plus a rich table.
        for r in rows:
            print(
                f"[{r.status}] {r.section}: {r.label}"
                + (f" — {r.detail}" if r.detail else "")
                + (f" → {r.remediation}" if r.remediation else "")
            )
        _render_rich(rows, Console(width=200, force_terminal=False))

    if _any_fail(rows):
        raise typer.Exit(1)
