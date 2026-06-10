"""Phase-0 empirical measurement: per-call Claude Code analysis latency by tier.

Runs the ACTUAL analysis runners (grammar/mishearing/keypoints/coverage/
coaching/consistency/followups) through the REAL claude binary, timing each, to
build the serial-vs-concurrent wall-clock model. CAPPED real calls (≤ ~14).
This is a manual measurement harness — NOT a test; the automated suite never
touches the real binary.

Run: uv run python specs/012-responsive-session-flow/research/measure_claude.py
"""
from __future__ import annotations
import time, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from speakloop.asr import Transcript
from speakloop.llm.claude_code_engine import ClaudeCodeEngine
from speakloop.feedback import cloud_prompt as _cp
from speakloop.feedback.grammar_analyzer import analyze
from speakloop.feedback import coach as _coach
from speakloop.coverage import keypoints as _kp
from speakloop.coverage import scoring as _cov
from speakloop.coverage.prompts import load_coverage_prompt, load_keypoints_prompt
from speakloop.interviewer import followups as _fu
from speakloop.interviewer.prompts import load_followups_prompt
from speakloop.triage import consistency as _cons
from speakloop.triage import mishearing as _mis
from speakloop.triage.prompts import load_consistency_prompt, load_triage_prompt
from speakloop.content import load
from speakloop.config import paths

qa = load(paths.resolve_qa_file())
q = qa.questions[0]

# Three plausible interview-answer transcripts (~answer to "four app components").
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
trs = [Transcript(text=t, words=[], audio_duration_seconds=60.0, vad_regions=[]) for t in T]

cloud_sp, _ = _cp.load_cloud_prompt()
coach_sp, _ = _cp.load_coach_prompt()
triage_sp, _ = load_triage_prompt()
cons_sp = load_consistency_prompt()
fu_sp, _ = load_followups_prompt()
kp_sp, _ = load_keypoints_prompt()
cov_sp, _ = load_coverage_prompt()

TIMEOUT = 240.0
strong = ClaudeCodeEngine(model="sonnet", timeout=TIMEOUT)
fast = ClaudeCodeEngine(model="haiku", timeout=TIMEOUT)

results = []
def timed(name, tier, fn):
    s = time.perf_counter()
    err = None
    out = None
    try:
        out = fn()
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    dt = time.perf_counter() - s
    n = (len(out) if isinstance(out, (list, str)) else "?")
    print(f"[{tier:6}] {name:14} {dt:7.2f}s  out_items={n}  err={err}")
    results.append({"call": name, "tier": tier, "seconds": round(dt, 2), "err": err})
    return out

print("== fast tier (haiku) ==")
timed("mishearing#1", "haiku", lambda: _mis.detect_mishearings(T[0], fast, system_prompt=triage_sp))
timed("mishearing#2", "haiku", lambda: _mis.detect_mishearings(T[2], fast, system_prompt=triage_sp))

print("== strong tier (sonnet) ==")
patterns = timed("grammar#1", "sonnet", lambda: analyze(trs, strong, system_prompt=cloud_sp))
timed("grammar#2", "sonnet", lambda: analyze(trs, strong, system_prompt=cloud_sp))
kpoints = timed("keypoints", "sonnet", lambda: _kp.derive_key_points(q.question, q.ideal_answer, "definition", strong, system_prompt=kp_sp))
if kpoints:
    timed("coverage", "sonnet", lambda: _cov.score_coverage(kpoints, trs, q.ideal_answer, strong, system_prompt=cov_sp, version=1))
coaching = timed("coaching", "sonnet", lambda: _coach.coach(q.question, trs, patterns or [], strong, system_prompt=coach_sp))
if coaching:
    timed("consistency", "sonnet", lambda: _cons.check_artifact(coaching, q.ideal_answer, strong, system_prompt=cons_sp))
timed("followups", "sonnet", lambda: _fu.generate_followups(q.question, trs, strong, system_prompt=fu_sp))

print("\n=== RAW RESULTS JSON ===")
print(json.dumps(results, indent=2))
Path(__file__).with_name("claude_timings.json").write_text(json.dumps(results, indent=2))
print(f"\nTOTAL real calls: {len(results)}")
