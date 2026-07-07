"""IMP-015 — `_provision_models` abort-vs-degrade contract (extracted from practice.run).

The base phase is REQUIRED (decline/failure → typer.Exit(1)); the optional local Phase-C
feedback model DEGRADES (prints, never raises). A cloud engine never fetches Phase C.
"""

from __future__ import annotations

import pytest
import typer
from rich.console import Console

from speakloop import installer
from speakloop.cli import practice

pytestmark = pytest.mark.unit


def _console() -> Console:
    return Console(quiet=True)


def _record(monkeypatch, *, fail_on: str | None = None, exc=None):
    phases: list[str] = []

    def _ensure(phase, *, console=None):
        phases.append(phase)
        if phase == fail_on:
            raise exc

    monkeypatch.setattr(installer, "ensure_models", _ensure)
    return phases


def test_base_decline_aborts(monkeypatch):
    _record(monkeypatch, fail_on="B", exc=installer.InstallDeclinedError("declined"))
    with pytest.raises(typer.Exit) as exc:
        practice._provision_models("local", listen_only=False, console=_console())
    assert exc.value.exit_code == 1


def test_base_failure_aborts(monkeypatch):
    _record(monkeypatch, fail_on="B", exc=installer.InstallFailedError("boom"))
    with pytest.raises(typer.Exit) as exc:
        practice._provision_models("local", listen_only=False, console=_console())
    assert exc.value.exit_code == 1


def test_cloud_engine_provisions_base_only(monkeypatch):
    phases = _record(monkeypatch)
    practice._provision_models("openrouter", listen_only=False, console=_console())
    assert phases == ["B"]  # a cloud engine never fetches the local Phase-C model


def test_local_full_session_provisions_base_and_c(monkeypatch):
    phases = _record(monkeypatch)
    practice._provision_models("local", listen_only=False, console=_console())
    assert phases == ["B", "C"]


def test_local_phase_c_decline_degrades_without_raising(monkeypatch):
    phases = _record(monkeypatch, fail_on="C", exc=installer.InstallDeclinedError("no llm"))
    # Must NOT raise — degrades to a recorded, resumable session (FR-009).
    practice._provision_models("local", listen_only=False, console=_console())
    assert phases == ["B", "C"]


def test_local_phase_c_failure_degrades_without_raising(monkeypatch):
    phases = _record(monkeypatch, fail_on="C", exc=installer.InstallFailedError("unavailable"))
    practice._provision_models("local", listen_only=False, console=_console())
    assert phases == ["B", "C"]


def test_listen_only_provisions_phase_a_only(monkeypatch):
    phases = _record(monkeypatch)
    practice._provision_models("local", listen_only=True, console=_console())
    assert phases == ["A"]  # listen-only needs no ASR and no Phase-C model


def test_decode_listen_key_case_sensitive_and_specials():
    """IMP-016: the listen-loop decode keeps r/R distinct (replay question vs ideal answer)
    and maps EOF/Enter → '' (next), Ctrl-C → 'q'."""
    assert practice._decode_listen_key(b"") == ""       # EOF on tty → next
    assert practice._decode_listen_key(b"\r") == ""      # Enter → next
    assert practice._decode_listen_key(b"\n") == ""
    assert practice._decode_listen_key(b"\x03") == "q"   # Ctrl-C → quit
    assert practice._decode_listen_key(b" ") == " "      # space → next
    assert practice._decode_listen_key(b"r") == "r"
    assert practice._decode_listen_key(b"R") == "R"      # case preserved, distinct from menu


def test_grammar_analysis_requires_all_fields():
    """IMP-017: a builder that forgets `engine` fails at CONSTRUCTION (the blind spot the
    old bolted-on `.engine`/`.runners` attributes hid), not by silently going serial."""
    with pytest.raises(TypeError):
        practice.GrammarAnalysis(runner=lambda ts: [], runners=None, coach=None)  # engine missing


def test_grammar_analysis_parallel_safe_reads_the_engine():
    class _Cloud:
        parallel_safe = True

    class _Local:
        parallel_safe = False

    def _mk(engine):
        return practice.GrammarAnalysis(runner=lambda ts: [], runners=None, engine=engine, coach=None)

    assert _mk(_Cloud()).parallel_safe is True
    assert _mk(_Local()).parallel_safe is False
    # The null "no model" sentinel has no engine → serial, and no runner.
    assert practice._NO_ANALYSIS.parallel_safe is False
    assert practice._NO_ANALYSIS.runner is None
