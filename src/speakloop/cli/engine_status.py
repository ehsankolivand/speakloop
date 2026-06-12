"""Shared active-engine readiness (015) — consumed by `doctor` and `setup`.

Reports, for the active feedback engine, what it needs to be "ready" and the next step
for anything missing. Imports only paths/manifest/validator/credentials and the
credit-free Claude probe (all function-local) — never one of the five engine packages —
so `speakloop --help` and the CLI import stay model-free (root CLAUDE.md O1 / Principle V).
"""

from __future__ import annotations

from dataclasses import dataclass

from speakloop.config import loop_config


@dataclass(frozen=True)
class Requirement:
    """One checkable need of an engine. `optional` requirements never fail an exit code."""

    label: str
    ok: bool
    detail: str
    next_step: str = ""
    optional: bool = False


@dataclass(frozen=True)
class EngineReadiness:
    engine: str
    requirements: list[Requirement]
    ready: bool  # all non-optional requirements satisfied


def active_engine() -> str:
    """The persisted default feedback engine (loop.yaml `engine:`, default `local`)."""
    return loop_config.load().engine


def engine_readiness(engine: str, *, claude_probe: dict | None = None) -> EngineReadiness:
    """Resolve the requirement list + overall readiness for `engine`.

    - local: the large local feedback model must be present (a hard requirement).
    - openrouter: an API token should be configured (optional — opt-in, never fails).
    - claude: the Claude Code CLI installed + logged in (optional — opt-in).

    ``claude_probe`` lets a caller (e.g. ``doctor``) inject an already-fetched
    ``claude_code_engine.doctor_probe()`` result so the credit-free ``claude`` subprocess
    runs once per command instead of once per section.
    """
    if engine == "local":
        requirements = [_local_llm_requirement()]
    elif engine == "openrouter":
        requirements = [_openrouter_requirement()]
    elif engine == "claude":
        requirements = _claude_requirements(claude_probe)
    else:  # unknown value — resolution falls back to local elsewhere; report nothing extra.
        requirements = []
    ready = all(r.ok for r in requirements if not r.optional)
    return EngineReadiness(engine=engine, requirements=requirements, ready=ready)


def _local_llm_requirement() -> Requirement:
    from speakloop.installer import manifest, validator

    result = validator.validate(manifest.QWEN3_14B_4BIT)
    if result.ok:
        return Requirement(
            label="local feedback model",
            ok=True,
            detail=f"{manifest.QWEN3_14B_4BIT.name} present",
        )
    return Requirement(
        label="local feedback model",
        ok=False,
        detail=f"{manifest.QWEN3_14B_4BIT.name} not downloaded",
        next_step="run `speakloop setup --engine local` (or `speakloop practice`) to download it.",
    )


def _openrouter_requirement() -> Requirement:
    from speakloop.llm import openrouter_credentials

    present = openrouter_credentials.resolve_token() is not None
    return Requirement(
        label="OpenRouter token",
        ok=present,
        optional=True,
        detail="configured (env or stored file)" if present else "not configured",
        next_step=(
            ""
            if present
            else "set OPENROUTER_API_KEY or run `speakloop practice --cloud` to be prompted."
        ),
    )


def _claude_requirements(probe: dict | None = None) -> list[Requirement]:
    info = probe
    if info is None:
        from speakloop.llm import claude_code_engine

        info = claude_code_engine.doctor_probe()
    if not info.get("installed"):
        return [
            Requirement(
                label="Claude Code CLI",
                ok=False,
                optional=True,
                detail="not found on PATH",
                next_step="install Claude Code to use `--engine claude`.",
            )
        ]
    logged_in = bool(info.get("logged_in"))
    return [
        Requirement(
            label="Claude Code CLI",
            ok=True,
            optional=True,
            detail=info.get("binary") or "installed",
        ),
        Requirement(
            label="Claude Code auth",
            ok=logged_in,
            optional=True,
            detail="logged in" if logged_in else "logged out",
            next_step="" if logged_in else "run `claude /login` to use `--engine claude`.",
        ),
    ]
