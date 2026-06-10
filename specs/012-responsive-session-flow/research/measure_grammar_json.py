"""013 — grammar JSON discipline: instrumented before/after measurement harness.

Runs the REAL `grammar_analyzer.analyze()` over the existing research fixture
transcripts, through the REAL Claude Code engine (sonnet), N times. Because it
calls the production `analyze()`, the bounded regenerate ACTUALLY FIRES when the
first pass fails to parse — so this measures TRUE end-to-end grammar latency and
the real regenerate rate, not a single-pass proxy.

Each run gets its OWN recording proxy over a SHARED stateless `ClaudeCodeEngine`,
so runs are thread-safe and may run concurrently. Every pass (first + any
regenerate) is captured: raw text, wall seconds, the `retry` flag. Per run the
harness records:

  * end-to-end wall seconds (all passes of that run),
  * whether the regenerate FIRED (>= 2 passes) — exact analyze() behavior,
  * the recovery-ladder rung the FIRST pass needed (`_extract_json` mirror),
  * the final verified/ranked GrammarPattern findings (analyze()'s return) — for
    the quality sanity check,
  * a fence-present flag; engine timeouts/errors are recorded too.

Because every grammar call is a SEPARATE `claude` subprocess, an individual run's
wall time is independent of how many other runs are in flight — so the per-call
latency distribution is directly comparable whether concurrency is 1 (serial) or
3 (matching the production analysis cap). Concurrency only shrinks total
wall-clock, not per-call latency.

The system prompt is read via the production path
`cloud_prompt.load_cloud_prompt()` — i.e. the SEEDED
~/.speakloop/openrouter_prompt.txt — so this harness measures whatever prompt is
currently deployed (old default before the edit, new default after).

Raw model output of every NON-clean first pass (rung != rung1, regenerate fired,
or terminal failure) is saved under grammar_raw_failures/.

Manual measurement harness, NOT a test; the automated suite never touches the
real binary.

Run:
  uv run python .../measure_grammar_json.py before 10 15 1   # serial, cap 15 calls
  uv run python .../measure_grammar_json.py after  10 13 3   # concurrency 3, cap 13
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import json_repair

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from speakloop.asr import Transcript
from speakloop.feedback import cloud_prompt as _cp
from speakloop.feedback.grammar_analyzer import (
    _looks_like_repetition_loop,
    _strip_code_fences,
    analyze,
)
from speakloop.llm import LLMEngineError
from speakloop.llm.claude_code_engine import ClaudeCodeEngine

HERE = Path(__file__).resolve().parent
FAIL_DIR = HERE / "grammar_raw_failures"
FAIL_DIR.mkdir(parents=True, exist_ok=True)

# Existing research fixture transcripts (the richer triple from measure_claude.py;
# answer to the Android "four app components" question, with realistic L2 errors).
T = [
    "So Android have four main component. The first one is Activity which is the screen "
    "user see. Then there is Service that run in background for long task. Also we have "
    "Broadcast Receiver that listen to system event like battery low. And the last one is "
    "Content Provider for sharing data between app.",
    "The four components are Activity, Service, Broadcast Receiver and Content Provider. "
    "Activity is a single screen with user interface. Service do work in background without "
    "UI, for example play music. Broadcast Receiver respond to broadcast announcement. "
    "Content Provider manage access to a structured set of data.",
    "Android applications are built from four component types. Activities present a UI and "
    "are the entry point for user interaction. Services run long-running operations in the "
    "background. Broadcast receivers handle system-wide events. Content providers expose a "
    "shared data layer that other apps can query through a consistent interface.",
]
TRS = [Transcript(text=t, words=[], audio_duration_seconds=60.0, vad_regions=[]) for t in T]


class RecordingEngine:
    """Per-run proxy over a shared stateless ClaudeCodeEngine; records each pass."""

    parallel_safe = True

    def __init__(self, inner: ClaudeCodeEngine) -> None:
        self._inner = inner
        self.calls: list[dict] = []
        self.attempts = 0  # real-call budget — counts timeouts/errors too

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        self.attempts += 1  # a call that times out still spent budget
        t0 = time.perf_counter()
        raw = self._inner.generate(
            system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature, retry=retry
        )
        self.calls.append({"retry": retry, "seconds": round(time.perf_counter() - t0, 2), "raw": raw})
        return raw


def classify_rung(raw_in: str) -> tuple[str, dict | None, bool]:
    """Mirror `grammar_analyzer._extract_json` exactly; report which rung won."""
    stripped = _strip_code_fences(raw_in.strip())
    fence_changed = stripped != raw_in.strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return "rung1_strict", obj, fence_changed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return "rung2_firstbrace_strict", obj, fence_changed
        except json.JSONDecodeError:
            pass
    try:
        repaired = json_repair.loads(stripped)
        if isinstance(repaired, dict) and repaired:
            return "rung3_jsonrepair_full", repaired, fence_changed
    except Exception:  # noqa: BLE001
        pass
    if match:
        try:
            repaired = json_repair.loads(match.group(0))
            if isinstance(repaired, dict) and repaired:
                return "rung4_jsonrepair_brace", repaired, fence_changed
        except Exception:  # noqa: BLE001
            pass
    return "FAIL_no_json", None, fence_changed


def patterns_to_json(patterns) -> list[dict]:
    return [
        {
            "label": p.label,
            "occurrence_count": p.occurrence_count,
            "impact_rank": p.impact_rank,
            "evidence": [{"quote": e["quote"], "corrected": e["corrected"]} for e in p.evidence],
        }
        for p in patterns
    ]


_print_lock = threading.Lock()


def run_one(idx: int, runs: int, tag: str, inner: ClaudeCodeEngine, cloud_sp: str, user_prompt: str) -> dict:
    rec_engine = RecordingEngine(inner)
    t0 = time.perf_counter()
    err = None
    patterns = []
    try:
        patterns = analyze(TRS, rec_engine, system_prompt=cloud_sp)
    except LLMEngineError as e:  # terminal: both passes failed → phase_c_error path
        err = f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001  — engine/auth/timeout
        err = f"{type(e).__name__}: {e}"
    dt = time.perf_counter() - t0

    passes = rec_engine.calls
    regen_fired = len(passes) >= 2
    first_raw = passes[0]["raw"] if passes else ""
    rung, _payload, fence = classify_rung(first_raw) if passes else ("NO_PASS", None, False)
    last_rung = classify_rung(passes[-1]["raw"])[0] if passes else "NO_PASS"
    clean = err is None and rung == "rung1_strict" and not regen_fired
    rec = {
        "run": idx,
        "tag": tag,
        "seconds": round(dt, 2),
        "passes": len(passes),
        "attempts": rec_engine.attempts,
        "pass_seconds": [c["seconds"] for c in passes],
        "regenerate_fired": regen_fired,
        "first_pass_rung": rung,
        "first_pass_strict": rung == "rung1_strict",
        "first_pass_fence_stripped": fence,
        "last_pass_rung": last_rung,
        "first_pass_repetition_loop": _looks_like_repetition_loop(first_raw) if passes else None,
        "n_patterns": len(patterns),
        "n_findings": sum(p.occurrence_count for p in patterns),
        "pattern_labels": sorted(p.label for p in patterns),
        "patterns": patterns_to_json(patterns),
        "err": err,
    }
    flag = "" if clean else "  !!"
    with _print_lock:
        line = (
            f"[{idx:2}/{runs}] {dt:6.1f}s passes={len(passes)} rung1={rung:24} "
            f"regen={regen_fired!s:5} fence={fence!s:5} pats={len(patterns)} "
            f"findings={rec['n_findings']}{flag}"
        )
        if err:
            line += f"  ERR={err[:60]}"
        print(line, flush=True)
    if not clean and passes:
        for j, c in enumerate(passes, start=1):
            (FAIL_DIR / f"{tag}_run{idx:02d}_pass{j}.txt").write_text(c["raw"] or "(empty)", encoding="utf-8")
    return rec


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "before"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    max_calls = int(sys.argv[3]) if len(sys.argv) > 3 else 25  # advisory ceiling (logged)
    concurrency = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    assert tag in ("before", "after"), "tag must be 'before' or 'after'"

    cloud_sp, prompt_path = _cp.load_cloud_prompt()
    prompt_sha = hashlib.sha256(cloud_sp.encode("utf-8")).hexdigest()[:12]
    inner = ClaudeCodeEngine(model="sonnet", timeout=240.0)
    user_prompt = None  # analyze() builds the user prompt internally; unused here
    from speakloop.feedback.grammar_analyzer import _user_prompt

    user_prompt = _user_prompt(TRS)

    print(f"== {tag.upper()} : {runs} runs, concurrency {concurrency}, ceiling {max_calls} calls ==")
    print(f"prompt path : {prompt_path}")
    print(f"prompt sha  : {prompt_sha}  ({len(cloud_sp)} chars)\n", flush=True)

    if concurrency <= 1:
        records = [run_one(i, runs, tag, inner, cloud_sp, user_prompt) for i in range(1, runs + 1)]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {ex.submit(run_one, i, runs, tag, inner, cloud_sp, user_prompt): i for i in range(1, runs + 1)}
            records = [f.result() for f in futs]
        records.sort(key=lambda r: r["run"])

    n = len(records)
    real_calls = sum(r["attempts"] for r in records)
    first_rung = sum(1 for r in records if r["first_pass_strict"])
    returning = [r for r in records if r["passes"] > 0]
    first_rung_of_returning = sum(1 for r in returning if r["first_pass_strict"])
    regens = sum(1 for r in records if r["regenerate_fired"])
    timeouts = sum(1 for r in records if r["err"] and "Timeout" in r["err"])
    secs = sorted(r["seconds"] for r in records)
    median = secs[len(secs) // 2] if secs else 0.0
    worst = max(secs) if secs else 0.0
    summary = {
        "tag": tag,
        "runs": n,
        "concurrency": concurrency,
        "real_calls": real_calls,
        "timeouts": timeouts,
        "prompt_sha": prompt_sha,
        "prompt_path": str(prompt_path),
        "first_rung_parse": f"{first_rung}/{n}",
        "first_rung_of_returning": f"{first_rung_of_returning}/{len(returning)}",
        "regenerate_fired": f"{regens}/{n}",
        "median_seconds": median,
        "worst_seconds": worst,
        "rung_counts": {
            rung: sum(1 for r in records if r["first_pass_rung"] == rung)
            for rung in sorted({r["first_pass_rung"] for r in records})
        },
        "records": records,
    }
    out_json = HERE / f"grammar_json_{tag}.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(f"first-pass strict (rung1)      : {first_rung}/{n}  (of returning: {first_rung_of_returning}/{len(returning)})")
    print(f"regenerate fired               : {regens}/{n}")
    print(f"timeouts (240s)                : {timeouts}")
    print(f"first-pass rung counts         : {summary['rung_counts']}")
    print(f"end-to-end median / worst      : {median:.1f}s / {worst:.1f}s")
    print(f"real claude calls spent        : {real_calls}")
    print(f"summary written                : {out_json}", flush=True)


if __name__ == "__main__":
    main()
