"""`speakloop doctor` — health-check (FR-024..FR-026)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass

import typer
from rich.console import Console
from rich.table import Table

from speakloop.audio import devices
from speakloop.cli import engine_status
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
    """Model presence rows, engine-aware (015).

    The local feedback model (Phase C / Qwen) is a FAIL-on-absence only when the active
    engine is ``local``; for a cloud active engine it renders informationally and never
    fails the exit code (a cloud user never needs it). TTS/ASR models stay FAIL-on-absence
    regardless. Every model row is always rendered (keeps `test_doctor_failure_modes`).
    """
    active = engine_status.active_engine()
    rows: list[CheckRow] = []
    for m in manifest.PHASE_C_MODELS:
        r = validator.validate(m)
        is_local_llm = m.required_for_phase == "C"
        path_detail = f"path: {m.local_path} (expected {r.expected_bytes:,} B)"
        if r.ok:
            status, detail, remediation = "OK", path_detail, ""
        elif is_local_llm and active != "local":
            status = "OK"
            detail = f"not required for the active engine ({active})"
            remediation = ""
        elif is_local_llm:
            status = "FAIL"
            detail = path_detail
            remediation = (
                "Run `speakloop setup --engine local` or `speakloop practice` to download this model."
            )
        else:
            status = "FAIL"
            detail = path_detail
            remediation = "Run `speakloop practice` to consent and download this model."
        rows.append(
            CheckRow(section="Models", label=m.name, status=status, detail=detail, remediation=remediation)
        )
    return rows


def _feedback_engine(claude_probe: dict | None = None) -> list[CheckRow]:
    """015: the active feedback engine + its readiness, with the exact next step.

    Cloud/claude requirement rows are non-failing (opt-in, matching the Cloud and Claude
    Code sections); a local engine missing its model fails (consistent with `_models`).
    ``claude_probe`` is the shared, once-per-run Claude Code probe (see `_collect`)."""
    active = engine_status.active_engine()
    readiness = engine_status.engine_readiness(active, claude_probe=claude_probe)
    rows = [
        CheckRow(
            section="Feedback engine",
            label="active engine",
            status="OK",
            detail=f"{active} (loop.yaml `engine:`; set with `speakloop setup`, override per run with --engine/--cloud)",
        )
    ]
    for req in readiness.requirements:
        if req.ok:
            status = "OK"
        elif req.optional:
            status = "WARN"
        else:
            status = "FAIL"
        rows.append(
            CheckRow(
                section="Feedback engine",
                label=req.label,
                status=status,
                detail=req.detail,
                remediation=req.next_step,
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


def _aria2() -> CheckRow:
    """007: report whether the parallel-download accelerator is on PATH."""
    binpath = shutil.which("aria2c")
    if binpath is None:
        return CheckRow(
            section="Install accelerator",
            label="aria2c",
            status="WARN",
            detail="not on PATH — falling back to single-connection downloader",
            remediation="install with 'brew install aria2' for faster, more resilient downloads",
        )
    try:
        out = subprocess.run(
            [binpath, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version_line = (out.stdout or out.stderr).splitlines()[0] if (out.stdout or out.stderr) else binpath
    except (OSError, subprocess.SubprocessError):
        version_line = binpath
    return CheckRow(
        section="Install accelerator",
        label="aria2c",
        status="OK",
        detail=version_line,
        remediation="",
    )


def _cloud() -> list[CheckRow]:
    """008: report optional cloud-mode configuration (never FAILs — it's opt-in).

    Imports are function-local so the module stays light. These resolvers touch
    only stdlib + pyyaml (already a dependency)."""
    from speakloop.llm import openrouter_config, openrouter_credentials

    model = openrouter_config.resolve_model()
    cfg = paths.openrouter_config_path()
    prompt = paths.openrouter_prompt_path()
    coach_prompt = paths.openrouter_coach_prompt_path()
    token_present = openrouter_credentials.resolve_token() is not None

    return [
        CheckRow(
            section="Cloud (OpenRouter)",
            label="model id",
            status="OK",
            detail=f"{model} (from {cfg if cfg.exists() else 'default'})",
            remediation=("" if cfg.exists() else f"edit `model:` in {cfg} to change (optional)."),
        ),
        CheckRow(
            section="Cloud (OpenRouter)",
            label="API token",
            status="OK" if token_present else "WARN",
            detail="present (env or stored file)" if token_present else "not configured",
            remediation=(
                ""
                if token_present
                else "set OPENROUTER_API_KEY or run `speakloop practice --cloud` to be prompted."
            ),
        ),
        CheckRow(
            section="Cloud (OpenRouter)",
            label="system prompt",
            status="OK",
            detail=f"{prompt}" + ("" if prompt.exists() else " (seeded on first cloud run)"),
            remediation="",
        ),
        CheckRow(
            section="Cloud (OpenRouter)",
            label="coach prompt",
            status="OK",
            detail=f"{coach_prompt}"
            + ("" if coach_prompt.exists() else " (seeded on first cloud run)"),
            remediation="",
        ),
    ]


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


def _interview_loop() -> list[CheckRow]:
    """010 Interview Loop: derived store + loop config + seeded analytic prompts."""
    store = paths.store_path()
    loop_cfg = paths.loop_config_path()
    rows = [
        CheckRow(
            section="Interview Loop",
            label=f"derived store: {store}",
            status="OK",
            detail="present (rebuildable via `speakloop rebuild`)" if store.exists()
            else "absent — built on first run / `speakloop rebuild`",
        ),
        CheckRow(
            section="Interview Loop",
            label=f"loop config: {loop_cfg}",
            status="OK",
            detail="present" if loop_cfg.exists() else "absent — built-in defaults (capacity 5)",
        ),
    ]
    prompts = {
        "follow-ups": paths.openrouter_followups_prompt_path(),
        "key points": paths.openrouter_keypoints_prompt_path(),
        "coverage": paths.openrouter_coverage_prompt_path(),
        "triage": paths.openrouter_triage_prompt_path(),
        "drill": paths.openrouter_drill_prompt_path(),
    }
    for name, p in prompts.items():
        rows.append(
            CheckRow(
                section="Interview Loop",
                label=f"{name} prompt",
                status="OK",
                detail=str(p) + ("" if p.exists() else " (seeded on first use)"),
            )
        )
    return rows


def _claude_code(probe: dict | None = None) -> list[CheckRow]:
    """011: report the Claude Code engine (opt-in; never FAILs the exit code).

    Probes are credit-free (`claude --version` + `claude auth status --json`); the
    whole probe is monkeypatched in tests so no automated test runs the real binary.
    ``probe`` is the shared, once-per-run result (see `_collect`)."""
    from speakloop.config import loop_config

    info = probe
    if info is None:
        from speakloop.llm import claude_code_engine

        info = claude_code_engine.doctor_probe()
    cfg_engine = loop_config.load().engine
    rows: list[CheckRow] = []

    if info["installed"]:
        rows.append(
            CheckRow(section="Claude Code", label="CLI binary", status="OK", detail=info["binary"])
        )
        rows.append(
            CheckRow(
                section="Claude Code",
                label="version",
                status="OK" if info["version"] else "WARN",
                detail=info["version"] or "unreadable",
                remediation="" if info["version"] else "run `claude update`.",
            )
        )
        if info["logged_in"]:
            method = info.get("auth_method") or "?"
            sub = info.get("subscription_type") or "?"
            rows.append(
                CheckRow(
                    section="Claude Code",
                    label="authentication",
                    status="OK",
                    detail=f"logged in ({method}, {sub})",
                )
            )
        else:
            rows.append(
                CheckRow(
                    section="Claude Code",
                    label="authentication",
                    status="WARN",
                    detail="logged out",
                    remediation="run `claude /login` to use `--engine claude`.",
                )
            )
    else:
        rows.append(
            CheckRow(
                section="Claude Code",
                label="CLI binary",
                status="WARN",
                detail="not found on PATH",
                remediation="install Claude Code to use `--engine claude` (optional).",
            )
        )

    rows.append(
        CheckRow(
            section="Claude Code",
            label="default engine",
            status="OK",
            detail=f"{cfg_engine} (loop.yaml `engine:`)",
        )
    )
    if info.get("api_key_in_env"):
        rows.append(
            CheckRow(
                section="Claude Code",
                label="ANTHROPIC_API_KEY",
                status="WARN",
                detail="set in environment",
                remediation="the claude engine strips it so calls bill to your subscription.",
            )
        )
    return rows


def _collect() -> list[CheckRow]:
    # Probe the Claude Code CLI once and share it across the sections that report it,
    # so a single `doctor` run never spawns the (credit-free) `claude` subprocess twice.
    from speakloop.llm import claude_code_engine

    claude_probe = claude_code_engine.doctor_probe()
    return [
        _python_runtime(),
        *_feedback_engine(claude_probe),
        *_models(),
        *_audio_devices(),
        _sessions_dir(),
        _aria2(),
        *_cloud(),
        *_interview_loop(),
        *_claude_code(claude_probe),
    ]


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
