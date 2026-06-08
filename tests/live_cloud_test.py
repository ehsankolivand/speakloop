"""Opt-in live smoke for the OpenRouter cloud engine (008).

Excluded from the default suite (addopts: `not live_cloud`). Run explicitly with
a real key, e.g.::

    OPENROUTER_API_KEY=sk-or-... uv run pytest -m live_cloud

Skips cleanly when no key is present, mirroring `live_download` / `live_asr`.
"""

from __future__ import annotations

import os

import pytest

from speakloop.llm.openrouter_engine import OpenRouterEngine

pytestmark = pytest.mark.live_cloud

_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()


@pytest.mark.skipif(not _KEY, reason="OPENROUTER_API_KEY not set")
def test_live_check_auth_and_generate():
    # A cheap, widely-available model for the smoke; override via env if desired.
    model = os.environ.get("SPEAKLOOP_LIVE_CLOUD_MODEL", "openai/gpt-4o-mini")
    eng = OpenRouterEngine(model=model, token=_KEY)
    eng.check_auth()  # raises on a bad token
    out = eng.generate(
        'Reply with the exact JSON {"errors": []} and nothing else.',
        "No transcripts.",
        max_tokens=64,
        temperature=0.0,
    )
    assert isinstance(out, str) and out.strip()
