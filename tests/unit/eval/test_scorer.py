"""T-E2 — scorer pure-function unit test (eval-set-format §3; data-model §6).

A hand-checked prediction↔gold example must compute matched/precision/recall/F0.5 and
exercise the overlap + label-compatibility match rule correctly. No model is involved.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_EVAL_PATH = REPO_ROOT / "eval" / "grammar" / "run_eval.py"


def _load_run_eval():
    spec = importlib.util.spec_from_file_location("run_eval", RUN_EVAL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_eval = _load_run_eval()
sys.path.insert(0, str(run_eval._SRC))
from speakloop.feedback import catalog as catalog_mod  # noqa: E402

CATALOG = catalog_mod.get_catalog()


def test_overlap_rule_case_insensitive_subset():
    assert run_eval._quotes_overlap("eight year", "eight year experience")
    assert run_eval._quotes_overlap("EIGHT YEAR EXPERIENCE", "eight year")
    assert not run_eval._quotes_overlap("eight year", "three principle")
    assert not run_eval._quotes_overlap("", "anything")


def test_labels_compatible_catalog_and_open_bucket():
    # Same catalog id → compatible.
    assert run_eval.labels_compatible(
        "plural/singular agreement", "plural-agreement", "plural/singular agreement", CATALOG
    )
    # Different catalog ids → not compatible.
    assert not run_eval.labels_compatible(
        "plural/singular agreement", "plural-agreement",
        "definite/indefinite article omission (common nouns)", CATALOG,
    )
    # Catalog prediction vs open-bucket gold → not compatible.
    assert not run_eval.labels_compatible(
        "plural/singular agreement", "plural-agreement", "adverb placement", CATALOG
    )
    # Both open-bucket, same surface label → compatible.
    assert run_eval.labels_compatible("adverb placement", None, "adverb placement", CATALOG)
    # Both open-bucket, different surface → not compatible.
    assert not run_eval.labels_compatible("adverb placement", None, "word order", CATALOG)


def test_score_case_hand_checked():
    gold = [
        {"attempt_ordinal": 1, "quote": "eight year", "label": "plural/singular agreement"},
        {"attempt_ordinal": 1, "quote": "like to programming", "label": "gerund/infinitive confusion"},
    ]
    predicted = [
        # matches gold[0] (overlap + same catalog id)
        {"attempt_ordinal": 1, "quote": "eight year experience",
         "label": "plural/singular agreement", "catalog_id": "plural-agreement"},
        # false alarm: different label, no gold to match
        {"attempt_ordinal": 1, "quote": "backend services",
         "label": "definite/indefinite article omission (common nouns)",
         "catalog_id": "article-omission-common"},
    ]
    matched, n_pred, n_gold = run_eval.score_case(predicted, gold, CATALOG)
    assert (matched, n_pred, n_gold) == (1, 2, 2)
    agg = run_eval.aggregate(matched, n_pred, n_gold)
    assert agg == {"precision": 0.5, "recall": 0.5, "f05": 0.5}


def test_match_is_one_to_one():
    # Two predictions overlapping the SAME single gold issue → only one match.
    gold = [{"attempt_ordinal": 1, "quote": "eight year", "label": "plural/singular agreement"}]
    predicted = [
        {"attempt_ordinal": 1, "quote": "eight year", "label": "plural/singular agreement",
         "catalog_id": "plural-agreement"},
        {"attempt_ordinal": 1, "quote": "eight year experience", "label": "plural/singular agreement",
         "catalog_id": "plural-agreement"},
    ]
    matched, n_pred, n_gold = run_eval.score_case(predicted, gold, CATALOG)
    assert matched == 1 and n_pred == 2 and n_gold == 1


def test_wrong_attempt_ordinal_does_not_match():
    gold = [{"attempt_ordinal": 1, "quote": "eight year", "label": "plural/singular agreement"}]
    predicted = [{"attempt_ordinal": 2, "quote": "eight year", "label": "plural/singular agreement",
                  "catalog_id": "plural-agreement"}]
    matched, _, _ = run_eval.score_case(predicted, gold, CATALOG)
    assert matched == 0


def test_f_beta_is_precision_weighted():
    # F0.5 must favor precision over recall.
    assert run_eval.f_beta(1.0, 0.5) > run_eval.f_beta(0.5, 1.0)
    assert round(run_eval.f_beta(1.0, 0.5), 4) == 0.8333
    assert round(run_eval.f_beta(0.5, 1.0), 4) == 0.5556
    assert run_eval.f_beta(0.0, 0.0) == 0.0


def test_aggregate_no_predictions_no_false_alarms():
    # A clean case (gold empty) with no predictions → perfect, no penalty.
    agg = run_eval.aggregate(0, 0, 0)
    assert agg["precision"] == 1.0 and agg["recall"] == 1.0
