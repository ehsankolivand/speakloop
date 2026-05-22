"""T-E1 — `run_eval.py --validate-only` enforces E1–E4 (eval-set-format Test obligations).

Model-free, CI-safe. The real set must validate clean; planted bad cases (non-verbatim
quote / unknown label / personal-path leak / wrong count) MUST fail the matching check.
The harness lives outside the package (`eval/`), so it is loaded by file path.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_EVAL_PATH = REPO_ROOT / "eval" / "grammar" / "run_eval.py"
REAL_CASES = REPO_ROOT / "eval" / "grammar" / "cases"


def _load_run_eval():
    spec = importlib.util.spec_from_file_location("run_eval", RUN_EVAL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_eval = _load_run_eval()


def _seed_valid(tmp: Path) -> Path:
    dst = tmp / "cases"
    shutil.copytree(REAL_CASES, dst)
    return dst


def test_real_set_validates_clean():
    assert run_eval.validate_set(REAL_CASES) == []


def test_cli_validate_only_exits_zero():
    assert run_eval.main(["--validate-only"]) == 0


def test_planted_non_verbatim_quote_fails_e1(tmp_path):
    dst = _seed_valid(tmp_path)
    (dst / "case-900.yaml").write_text(
        "id: case-900\nsource: synthetic\nl1: persian\n"
        'transcripts:\n  - "I work on backend systems."\n'
        "gold_issues:\n  - attempt_ordinal: 1\n"
        '    quote: "this text is not in the transcript"\n'
        '    label: "plural/singular agreement"\n',
        encoding="utf-8",
    )
    errors = run_eval.validate_set(dst)
    assert any(e.startswith("E1") for e in errors), errors


def test_planted_unknown_label_fails_e2(tmp_path):
    dst = _seed_valid(tmp_path)
    (dst / "case-901.yaml").write_text(
        "id: case-901\nsource: synthetic\nl1: persian\n"
        'transcripts:\n  - "I work on backend systems."\n'
        "gold_issues:\n  - attempt_ordinal: 1\n"
        '    quote: "work on backend"\n'
        '    label: "florp"\n',
        encoding="utf-8",
    )
    errors = run_eval.validate_set(dst)
    assert any(e.startswith("E2") for e in errors), errors


def test_planted_personal_path_leak_fails_e3(tmp_path):
    dst = _seed_valid(tmp_path)
    # Build the leaking path from parts so this SOURCE file contains no contiguous
    # "/Users/<name>/" string (which the repo-wide path audit would otherwise flag);
    # the runtime value still triggers the E3 scan inside validate_set.
    leak = "/Users/" + "someone" + "/secret/file.yaml"
    (dst / "case-902.yaml").write_text(
        "id: case-902\nsource: synthetic\nl1: persian\n"
        'transcripts:\n  - "I work on backend systems."\n'
        "gold_issues: []\n"
        f'notes: "saved under {leak}"\n',
        encoding="utf-8",
    )
    errors = run_eval.validate_set(dst)
    assert any(e.startswith("E3") for e in errors), errors


def test_count_out_of_range_fails_e4(tmp_path):
    dst = tmp_path / "cases"
    dst.mkdir()
    # Copy only 3 real cases → below the 20-case floor.
    for p in sorted(REAL_CASES.glob("*.yaml"))[:3]:
        shutil.copy(p, dst / p.name)
    errors = run_eval.validate_set(dst)
    assert any(e.startswith("E4") for e in errors), errors


def test_validate_does_not_import_engine_packages():
    """validate-only must touch no engine package (model-free)."""
    import sys

    run_eval.validate_set(REAL_CASES)
    assert "mlx_lm" not in sys.modules
