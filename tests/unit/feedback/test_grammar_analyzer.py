"""T019 — catalog-aware grammar analyzer over the gold set (LLM stubbed).

Replays the human-labelled gold-set transcripts through the analyzer with a
stubbed LLM and asserts SC-002 (catalog-accurate labels, verbatim + coherent
evidence, garble dropped, impact-ordered, one Top priority) and SC-003
(corrected-coverage ratio >= 0.8).
"""

from __future__ import annotations

import json

import pytest
import yaml

from speakloop.asr import Transcript
from speakloop.feedback import grammar_analyzer, narrative
from speakloop.feedback.frontmatter import Attempt, AttemptMetrics
from speakloop.llm.interface import LLMEngineError

pytestmark = pytest.mark.unit


def _gold(transcript_fixture):
    return yaml.safe_load(transcript_fixture("gold_set.yaml").read_text(encoding="utf-8"))


def _transcripts(gold) -> list[Transcript]:
    t = gold["transcripts"]
    return [
        Transcript(text=t["attempt_1"], audio_duration_seconds=60.0),
        Transcript(text=t["attempt_2"], audio_duration_seconds=45.0),
        Transcript(text=t["attempt_3"], audio_duration_seconds=30.0),
    ]


def _stub_payload(gold) -> str:
    """Build the LLM's would-be JSON from the gold cases + the garble it must drop."""
    patterns = []
    # occurrence_count chosen so the impact tie between the two rank-2 patterns
    # is broken by frequency (gerund, occ 3, sorts before comparative, occ 1).
    counts = {"gerund": 3, "plural": 1, "comparative": 1}
    for case in gold["catalog_cases"]:
        patterns.append(
            {
                "label": case["expected_label"],
                "occurrence_count": counts[case["id"]],
                "evidence": [
                    {
                        "attempt_ordinal": case["attempt_ordinal"],
                        "quote": case["quote"],
                        "corrected": case["corrected"],
                    }
                ],
            }
        )
    # A hallucinated pattern citing ASR garble — must be dropped (FR-006).
    for g in gold["garble_cases"]:
        patterns.append(
            {
                "label": "incoherent fragment",
                "occurrence_count": 2,
                "explanation": "n/a",
                "evidence": [{"attempt_ordinal": g["attempt_ordinal"], "quote": g["quote"]}],
            }
        )
    return json.dumps({"patterns": patterns})


class _StubLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        return self._response


def _good_fluency_attempts() -> list[Attempt]:
    return [
        Attempt(
            ordinal=i,
            time_budget_seconds={1: 240, 2: 180, 3: 120}[i],
            actual_duration_seconds=100.0,
            transcript="x",
            metrics=AttemptMetrics(
                words_total=120,
                speech_rate_wpm=120.0 + 6 * i,
                filler_words_count=2,
                filler_density_per_100_words=2.0,
                pauses_count=3,
                mean_pause_ms=500.0,
                self_corrections_count=0,
            ),
        )
        for i in (1, 2, 3)
    ]


def test_gold_set_labels_are_catalog_accurate(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    patterns = grammar_analyzer.analyze(ts, _StubLLM(_stub_payload(gold)))

    by_label = {p.label: p for p in patterns}
    for case in gold["catalog_cases"]:
        assert case["expected_label"] in by_label, f"missing {case['expected_label']}"
        p = by_label[case["expected_label"]]
        assert p.catalog_id == case["expected_catalog_id"]
        assert p.impact_rank == case["expected_impact_rank"]
        assert p.explanation and p.explanation.strip()  # catalog transfer_reason


def test_evidence_is_verbatim_and_coherent_and_corrected(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    patterns = grammar_analyzer.analyze(ts, _StubLLM(_stub_payload(gold)))

    for p in patterns:
        for ev in p.evidence:
            ordinal = ev["attempt_ordinal"]
            assert ev["quote"] in ts[ordinal - 1].text  # FR-007 verbatim
            if "corrected" in ev:
                assert ev["corrected"] != ev["quote"]  # FR-009


def test_garble_evidence_is_dropped(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    patterns = grammar_analyzer.analyze(ts, _StubLLM(_stub_payload(gold)))

    all_quotes = [ev["quote"] for p in patterns for ev in p.evidence]
    assert "Killing RT check" not in all_quotes
    # The pattern that cited only garble is gone entirely.
    assert "incoherent fragment" not in {p.label for p in patterns}


def test_patterns_are_impact_ordered(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    patterns = grammar_analyzer.analyze(ts, _StubLLM(_stub_payload(gold)))

    ranks = [p.impact_rank for p in patterns]
    assert ranks == sorted(ranks)
    # Tie at rank 2 broken by frequency: gerund (3x) before comparative (1x).
    labels = [p.label for p in patterns]
    assert labels.index("gerund/infinitive confusion") < labels.index("comparative form error")


def test_exactly_one_top_priority_surfaced(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    patterns = grammar_analyzer.analyze(ts, _StubLLM(_stub_payload(gold)))

    top = narrative.select_top_priority(patterns, _good_fluency_attempts())
    assert isinstance(top, str) and top.strip()
    # Highest-impact grammar pattern wins (gerund, rank 2, most frequent).
    assert "gerund/infinitive confusion" in top


def test_corrected_coverage_ratio_meets_sc003(transcript_fixture):
    """SC-003: >= 80% of reported fixes reference the user's words + a concrete fix."""
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    patterns = grammar_analyzer.analyze(ts, _StubLLM(_stub_payload(gold)))

    total_fixes = sum(len(p.evidence) for p in patterns)
    anchored_fixes = sum(
        1
        for p in patterns
        for ev in p.evidence
        if ev.get("corrected") and ev["corrected"] != ev["quote"] and ev["quote"] in ts[ev["attempt_ordinal"] - 1].text
    )
    assert total_fixes > 0
    assert anchored_fixes / total_fixes >= 0.8


def test_open_bucket_requires_count_two(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    payload = json.dumps(
        {
            "patterns": [
                {
                    "label": "some novel non-catalog pattern",
                    "occurrence_count": 1,
                    "explanation": "a real reason",
                    "evidence": [{"attempt_ordinal": 1, "quote": "I work on Android apps", "corrected": "I work on the Android app"}],
                }
            ]
        }
    )
    assert grammar_analyzer.analyze(ts, _StubLLM(payload)) == []


def test_open_bucket_without_explanation_dropped(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    payload = json.dumps(
        {
            "patterns": [
                {
                    "label": "novel recurring pattern",
                    "occurrence_count": 2,
                    "evidence": [
                        {"attempt_ordinal": 1, "quote": "I work on Android apps", "corrected": "I work on the Android app"},
                        {"attempt_ordinal": 2, "quote": "I build payment", "corrected": "I build payments"},
                    ],
                }
            ]
        }
    )
    # No explanation supplied for an open-bucket pattern → dropped (contract).
    assert grammar_analyzer.analyze(ts, _StubLLM(payload)) == []


def test_fix_equal_to_quote_is_suppressed(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    payload = json.dumps(
        {
            "patterns": [
                {
                    "label": "gerund/infinitive confusion",
                    "occurrence_count": 1,
                    "evidence": [
                        {"attempt_ordinal": 1, "quote": "I like to programming", "corrected": "I like to programming"}
                    ],
                }
            ]
        }
    )
    # The only correction equals the quote → no real fix → suppressed (FR-009).
    assert grammar_analyzer.analyze(ts, _StubLLM(payload)) == []


def test_duplicate_patterns_are_merged(transcript_fixture):
    """FR-004 (006): two emissions of the same catalog pattern merge into one card —
    no repeated restatement reaches the report. V1–V5 are unweakened by the merge."""
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)
    payload = json.dumps(
        {
            "patterns": [
                {
                    "label": "gerund/infinitive confusion",
                    "occurrence_count": 1,
                    "evidence": [
                        {"attempt_ordinal": 1, "quote": "I like to programming", "corrected": "I like programming"}
                    ],
                },
                {
                    "label": "gerund/infinitive confusion",
                    "occurrence_count": 1,
                    "evidence": [
                        {"attempt_ordinal": 1, "quote": "I like to programming", "corrected": "I like programming"}
                    ],
                },
            ]
        }
    )
    patterns = grammar_analyzer.analyze(ts, _StubLLM(payload))
    gerunds = [p for p in patterns if p.label == "gerund/infinitive confusion"]
    assert len(gerunds) == 1  # merged, not two duplicate cards
    assert len(gerunds[0].evidence) == 1  # identical evidence unioned, not doubled
    assert gerunds[0].occurrence_count == 2  # counts summed (FR-004)


def test_think_tag_in_response_is_rejected(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)

    class _LLM:
        def generate(self, *_a, **_k):
            return "<think>nope</think>" + json.dumps({"patterns": []})

    with pytest.raises(LLMEngineError):
        grammar_analyzer.analyze(ts, _LLM())


def test_malformed_response_raises(transcript_fixture):
    gold = _gold(transcript_fixture)
    ts = _transcripts(gold)

    class _LLM:
        def generate(self, *_a, **_k):
            return "not json at all"

    with pytest.raises(LLMEngineError):
        grammar_analyzer.analyze(ts, _LLM())
