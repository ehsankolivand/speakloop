"""T028 — consent prompt is decline-by-default (FR-019, FR-020)."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop.installer.consent import prompt_for_consent
from speakloop.installer.manifest import KOKORO_82M, PARAKEET_TDT_06B_V3

pytestmark = pytest.mark.unit


def _capture_console() -> Console:
    return Console(file=io.StringIO(), force_terminal=False, width=120)


@pytest.mark.parametrize("answer", ["n", "", "no", "NOPE", "garbage"])
def test_declines_by_default(answer):
    out = []
    result = prompt_for_consent(
        [KOKORO_82M],
        console=_capture_console(),
        input_fn=lambda _prompt: (out.append(_prompt), answer)[1],
    )
    assert result is False


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES"])
def test_consents_on_explicit_yes(answer):
    result = prompt_for_consent(
        [KOKORO_82M],
        console=_capture_console(),
        input_fn=lambda _p: answer,
    )
    assert result is True


def test_eof_declines():
    def raise_eof(_p):
        raise EOFError

    result = prompt_for_consent([KOKORO_82M], console=_capture_console(), input_fn=raise_eof)
    assert result is False


def test_output_includes_size_and_total():
    console_buf = io.StringIO()
    console = Console(file=console_buf, force_terminal=False, width=200)
    prompt_for_consent(
        [KOKORO_82M, PARAKEET_TDT_06B_V3],
        console=console,
        input_fn=lambda _p: "n",
    )
    text = console_buf.getvalue()
    assert "Kokoro-82M" in text
    assert "Parakeet-TDT-0.6b-v3" in text
    assert "Total disk footprint" in text
