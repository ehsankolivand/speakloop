#!/usr/bin/env python3
"""Offline grammar-eval harness (feature 006-feedback-quality-reliability).

Two instruments in one tool (contracts/eval-set-format.md):

* ``--validate-only`` — model-free self-check of the eval set (E1–E4 + path-leak
  scan). CI-safe, deterministic, touches no model. Exits non-zero on any failure.
* ``--phase {pre,post}`` — on-device measurement against the **already-downloaded**
  local model. Scores grammar **agreement** (precision/recall/F0.5) on the 20–30
  labeled ``cases/`` and the **failure rate** on the ≥100-session ``failure_batch/``
  in one pass, then writes a baseline record. Each unit is run ``--runs K`` times
  (temperature 0.7 is stochastic) and the per-unit **median** is used.

Offline (Principle II): the live path loads only the local model; if it is absent
the harness prints ``model unavailable — skipped`` and exits non-zero **without** a
network fetch. This file lives outside ``src/speakloop`` and is NEVER shipped.

The scorer functions (``match_predicted_to_gold``, ``score_case``, ``f_beta``,
``aggregate``) are pure and importable (no model) — see tests/unit/eval/test_scorer.py.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

# --- locate the package: eval/ is OUTSIDE src/, so put src/ on the path -------
REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

HERE = Path(__file__).parent
CASES_DIR = HERE / "cases"
FAILURE_DIR = HERE / "failure_batch"

MODEL_ID = "mlx-community/Qwen3-8B-4bit"  # Decision 2: 4-bit, no swap (FR-017)
QUANT = "4bit"

# Controlled open-bucket vocabulary (PROTOCOL.md §2). A gold ``label`` is valid
# iff it is a catalog label OR one of these — keeps E2 falsifiable (an unknown
# label such as "florp" must fail validation, per T-E1).
OPEN_BUCKET_LABELS = {
    "verb tense error",
    "adverb placement",
    "word order",
    "subject-verb agreement",
    "negation form",
    "tense agreement",
}

# Machine-specific path leaks (mirror tests/integration/test_path_portability_audit.py).
_LEAK_PATTERNS = (
    re.compile(r"(?:/Users/|/home/)[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\"),
)

F_BETA = 0.5  # F0.5: precision-weighted (a false alarm costs a learner more — SC-002)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_cases(cases_dir: Path = CASES_DIR) -> list[dict]:
    return [_load_yaml(p) for p in sorted(cases_dir.glob("*.yaml"))]


def load_failure_batch(batch_dir: Path = FAILURE_DIR) -> list[dict]:
    return [_load_yaml(p) for p in sorted(batch_dir.glob("*.yaml"))]


def _catalog_labels() -> set[str]:
    from speakloop.feedback import catalog as catalog_mod

    return {e.label for e in catalog_mod.get_catalog().entries}


# --------------------------------------------------------------------------- #
# Validation — E1..E4 (model-free)
# --------------------------------------------------------------------------- #
def validate_set(cases_dir: Path = CASES_DIR) -> list[str]:
    """Return a list of human-readable validation errors ([] == valid)."""
    errors: list[str] = []
    catalog_labels = _catalog_labels()
    allowed = catalog_labels | OPEN_BUCKET_LABELS

    files = sorted(cases_dir.glob("*.yaml"))
    n = len(files)
    # E4 — count and per-case shape
    if not (20 <= n <= 30):
        errors.append(f"E4: case count {n} outside 20..30")
    empty_gold = 0

    for path in files:
        text = path.read_text(encoding="utf-8")
        # E3 — no machine-specific path leak in the file text
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pat.search(line) for pat in _LEAK_PATTERNS):
                errors.append(f"E3: {path.name}:{lineno} machine-specific path leak")
        d = yaml.safe_load(text) or {}
        ts = d.get("transcripts") or []
        if not ts or not any(str(t).strip() for t in ts):
            errors.append(f"E4: {path.name} has no non-empty transcript")
        gold = d.get("gold_issues") or []
        if not gold:
            empty_gold += 1
        for g in gold:
            o = g.get("attempt_ordinal")
            quote = g.get("quote", "")
            label = g.get("label", "")
            # E1 — verbatim substring of the referenced transcript
            if not isinstance(o, int) or o < 1 or o > len(ts):
                errors.append(f"E1: {path.name} bad attempt_ordinal {o!r}")
            elif quote not in ts[o - 1]:
                errors.append(f"E1: {path.name} quote {quote!r} not verbatim in attempt {o}")
            # E2 — known catalog label or controlled open-bucket label
            if label not in allowed:
                errors.append(f"E2: {path.name} unknown label {label!r}")

    if empty_gold == 0 and n > 0:
        errors.append("E4: no empty-gold (correct-answer) cases — add some to measure false alarms")
    return errors


# --------------------------------------------------------------------------- #
# Scoring — pure functions (no model). See test_scorer.py (T-E2).
# --------------------------------------------------------------------------- #
def _quotes_overlap(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return False
    return a in b or b in a


def labels_compatible(pred_label: str, pred_catalog_id, gold_label: str, catalog) -> bool:
    """Compatible iff same catalog id, or both open-bucket with equal surface label."""
    gold_entry = catalog.get(gold_label)
    gold_catalog_id = gold_entry.id if gold_entry is not None else None
    if pred_catalog_id is not None or gold_catalog_id is not None:
        return pred_catalog_id == gold_catalog_id and pred_catalog_id is not None
    # both open-bucket: same surface type ≈ same normalized label
    return pred_label.strip().lower() == gold_label.strip().lower()


def predicted_issues_from_patterns(patterns) -> list[dict]:
    """Flatten analyzer GrammarPatterns into per-evidence predicted issues."""
    issues: list[dict] = []
    for p in patterns:
        for ev in p.evidence:
            issues.append(
                {
                    "attempt_ordinal": ev.get("attempt_ordinal"),
                    "quote": ev.get("quote", ""),
                    "label": p.label,
                    "catalog_id": p.catalog_id,
                }
            )
    return issues


def match_predicted_to_gold(predicted: list[dict], gold: list[dict], catalog) -> int:
    """Greedy 1:1 matching; returns the number of matched gold issues."""
    used_pred: set[int] = set()
    matched = 0
    for g in gold:
        for i, pred in enumerate(predicted):
            if i in used_pred:
                continue
            if pred.get("attempt_ordinal") != g.get("attempt_ordinal"):
                continue
            if not _quotes_overlap(pred.get("quote", ""), g.get("quote", "")):
                continue
            if not labels_compatible(
                pred.get("label", ""), pred.get("catalog_id"), g.get("label", ""), catalog
            ):
                continue
            used_pred.add(i)
            matched += 1
            break
    return matched


def score_case(predicted: list[dict], gold: list[dict], catalog) -> tuple[int, int, int]:
    """Return (matched, n_predicted, n_gold) for one case."""
    matched = match_predicted_to_gold(predicted, gold, catalog)
    return matched, len(predicted), len(gold)


def f_beta(precision: float, recall: float, beta: float = F_BETA) -> float:
    b2 = beta * beta
    denom = b2 * precision + recall
    if denom == 0:
        return 0.0
    return (1 + b2) * precision * recall / denom


def aggregate(sum_matched: float, sum_pred: float, sum_gold: float) -> dict:
    precision = sum_matched / sum_pred if sum_pred > 0 else 1.0
    recall = sum_matched / sum_gold if sum_gold > 0 else 1.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f05": round(f_beta(precision, recall), 4),
    }


# --------------------------------------------------------------------------- #
# Eval-set version stamp
# --------------------------------------------------------------------------- #
def eval_set_version(cases_dir: Path = CASES_DIR) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD:eval/grammar/cases"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:  # noqa: BLE001 — git optional; fall back to content hash
        pass
    h = hashlib.sha256()
    for f in sorted(cases_dir.glob("*.yaml")):
        h.update(f.read_bytes())
    return "sha256:" + h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Live measurement (offline; --phase)
# --------------------------------------------------------------------------- #
def model_available() -> bool:
    """True iff mlx_lm is importable AND the local model dir exists. No network."""
    if importlib.util.find_spec("mlx_lm") is None:
        return False
    try:
        from speakloop.installer.manifest import QWEN3_8B_4BIT

        return QWEN3_8B_4BIT.local_path.exists()
    except Exception:  # noqa: BLE001
        return False


def _seed_engine() -> None:
    """Seed mlx where allowed so a whole run is reproducible (still stochastic per draw)."""
    try:
        import mlx.core as mx  # type: ignore

        mx.random.seed(0)
    except Exception:  # noqa: BLE001 — seeding is best-effort
        pass


def _analyze_once(transcripts_text: list[str], llm):
    """Run the real analyzer on one session. Returns (patterns, failed: bool)."""
    from speakloop.asr import Transcript
    from speakloop.feedback import grammar_analyzer

    ts = [Transcript(text=t, audio_duration_seconds=60.0) for t in transcripts_text]
    try:
        patterns = grammar_analyzer.analyze(ts, llm)
        return patterns, False
    except Exception:  # noqa: BLE001 — any raise == would fall back to Phase-B (SC-001 failure)
        return [], True


def measure(phase: str, runs: int) -> dict:
    from speakloop.feedback import catalog as catalog_mod
    from speakloop.llm.qwen_engine import QwenEngine

    catalog = catalog_mod.get_catalog()
    _seed_engine()
    llm = QwenEngine()

    cases = load_cases()
    batch = load_failure_batch()

    # --- agreement on labeled cases (per-case median over K runs) ---
    sum_matched = sum_pred = sum_gold = 0.0
    for c in cases:
        ts = c.get("transcripts") or []
        gold = c.get("gold_issues") or []
        per_run_matched: list[int] = []
        per_run_pred: list[int] = []
        for _ in range(runs):
            patterns, failed = _analyze_once(ts, llm)
            predicted = [] if failed else predicted_issues_from_patterns(patterns)
            m, p, _g = score_case(predicted, gold, catalog)
            per_run_matched.append(m)
            per_run_pred.append(p)
        sum_matched += statistics.median(per_run_matched)
        sum_pred += statistics.median(per_run_pred)
        sum_gold += len(gold)
    grammar = aggregate(sum_matched, sum_pred, sum_gold)

    # --- failure rate on the unlabeled batch (per-session majority over K runs) ---
    failed_sessions = 0
    for s in batch:
        ts = s.get("transcripts") or []
        fails = sum(1 for _ in range(runs) if _analyze_once(ts, llm)[1])
        if fails > runs / 2:  # median outcome
            failed_sessions += 1
    failure_rate = round(failed_sessions / len(batch), 4) if batch else 0.0

    return {
        "captured_at": datetime.now(UTC).date().isoformat(),
        "phase": phase,
        "model_id": MODEL_ID,
        "quant": QUANT,
        "eval_set_version": eval_set_version(),
        "runs_per_case": runs,
        "failure_batch_size": len(batch),
        "failure_rate": failure_rate,
        "n_labeled_cases": len(cases),
        "grammar": grammar,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline grammar-eval harness (feature 006).")
    ap.add_argument("--validate-only", action="store_true", help="E1–E4 self-check, no model.")
    ap.add_argument("--phase", choices=["pre", "post"], help="Measure against the local model.")
    ap.add_argument("--runs", type=int, default=3, help="K repeated runs per unit (median).")
    ap.add_argument("--out", type=Path, help="Write the baseline record YAML here.")
    args = ap.parse_args(argv)

    if args.validate_only or not args.phase:
        errors = validate_set()
        if errors:
            print(f"eval-set validation FAILED ({len(errors)} issue(s)):")
            for e in errors:
                print(f"  - {e}")
            return 1
        print(f"eval-set validation OK — {len(load_cases())} cases, "
              f"{len(load_failure_batch())} failure-batch sessions")
        if args.validate_only:
            return 0

    # Live measurement
    if not model_available():
        print("model unavailable — skipped")  # offline: no network fetch (Principle II)
        return 2

    record = measure(args.phase, args.runs)
    body = yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")
        print(f"wrote {args.out}")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
