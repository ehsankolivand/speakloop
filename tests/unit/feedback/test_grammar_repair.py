"""T-G1 / T-G2 — JSON parse + json-repair recovery (grammar-output-schema §A,§C).

T-G1: a golden well-formed flat-schema response parses with ZERO repair.
T-G2: every bad-JSON fixture (tests/unit/feedback/fixtures/bad_json/) recovers via
      json-repair to the same parsed payload AND the same verified patterns as a clean
      parse. Cached fixtures + a stub LLM — no live model (Constitution Dev Guidelines).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from speakloop.asr import Transcript
from speakloop.feedback import grammar_analyzer as ga

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures" / "bad_json"

GOLDEN = (
    '{"errors": [{"attempt_ordinal": 1, "quote": "like to programming", '
    '"corrected": "like programming", "error_type": "gerund/infinitive confusion", '
    '"explanation": "After like, use the -ing form."}]}'
)
# A transcript that contains the evidence quote verbatim + coherently.
TS = [Transcript(text="I like to programming every day at work here.", audio_duration_seconds=60.0)]


class _StubLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, **kwargs):
        return self._response


def _fixtures():
    return sorted(FIXTURES.glob("*.yaml"))


def _patterns_repr(patterns):
    return [
        (p.label, p.occurrence_count, p.catalog_id, tuple(sorted((e["attempt_ordinal"], e["quote"], e.get("corrected")) for e in p.evidence)))
        for p in patterns
    ]


# --- T-G1: golden well-formed flat schema parses with ZERO repair ------------


def test_golden_parses_with_zero_repair(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("json_repair must NOT run on clean, well-formed JSON")

    monkeypatch.setattr(ga.json_repair, "loads", boom)
    payload = ga._extract_json(GOLDEN)
    assert payload["errors"][0]["error_type"] == "gerund/infinitive confusion"


def test_golden_yields_verified_pattern():
    patterns = ga.analyze(TS, _StubLLM(GOLDEN))
    assert len(patterns) == 1
    assert patterns[0].label == "gerund/infinitive confusion"
    assert patterns[0].evidence[0]["quote"] == "like to programming"
    assert patterns[0].evidence[0]["corrected"] == "like programming"


# --- T-G2: every bad fixture recovers to the same payload + verified patterns -


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.stem)
def test_fixture_parse_recovers_to_expected(path):
    fx = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert ga._extract_json(fx["raw"]) == fx["expected"], path.name


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.stem)
def test_fixture_yields_same_verified_patterns_as_clean(path):
    fx = yaml.safe_load(path.read_text(encoding="utf-8"))
    clean = json.dumps(fx["expected"])
    from_bad = ga.analyze(TS, _StubLLM(fx["raw"]))
    from_clean = ga.analyze(TS, _StubLLM(clean))
    assert _patterns_repr(from_bad) == _patterns_repr(from_clean)
    # And the recovery actually produced a usable pattern (not empty).
    assert from_bad and from_bad[0].label == "gerund/infinitive confusion"


def test_corpus_is_non_trivial():
    # Guards against an empty fixtures dir silently passing the parametrized tests.
    assert len(_fixtures()) >= 8
