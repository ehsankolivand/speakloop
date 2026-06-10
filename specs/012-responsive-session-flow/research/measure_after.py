"""Phase-6 AFTER measurement: concurrent analysis wall-clock via the real executor.

Runs coordinator._analyze ONCE in CONCURRENT mode (claude, cap 3) over a real
transcript, using the real runners, and reports the measured analysis wall-clock +
per-stage timings. Compared against the serial baseline already measured in
research/claude_timings.json. ~8 capped real claude calls.

Run: uv run python specs/012-responsive-session-flow/research/measure_after.py
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from rich.console import Console
from speakloop.asr import Transcript
from speakloop.content import load
from speakloop.config import paths
from speakloop.feedback import cloud_prompt as _cp
from speakloop.feedback.grammar_analyzer import analyze
from speakloop.feedback import coach as _coach
from speakloop.llm.claude_code_engine import ClaudeCodeEngine
from speakloop.feedback.timings import StageTimer
from speakloop.sessions import coordinator
from speakloop.cli import practice as _practice
from speakloop.triage import hallucination as _halluc

qa = load(paths.resolve_qa_file())
q = qa.questions[0]
T = [
 "So Android have four main component. The first one is Activity which is the screen "
 "user see. Then Service that run in background. Also Broadcast Receiver that listen to "
 "system event. And the last one is Content Provider for sharing data between app.",
 "The four components are Activity, Service, Broadcast Receiver and Content Provider. "
 "Activity is a single screen with user interface. Service do work in background.",
 "Android applications are built from four component types. Activities present a UI. "
 "Services run long-running operations. Broadcast receivers handle system-wide events. "
 "Content providers expose a shared data layer.",
]
real_transcripts = [Transcript(text=t, audio_duration_seconds=60.0) for t in T]
triaged = [_halluc.filter_hallucinations(Transcript(text=t, audio_duration_seconds=60.0)) for t in T]

timeout = 240.0
strong = ClaudeCodeEngine(model="sonnet", timeout=timeout)
fast = ClaudeCodeEngine(model="haiku", timeout=timeout)
cloud_sp, _ = _cp.load_cloud_prompt()
coach_sp, _ = _cp.load_coach_prompt()

def grammar_analyzer(ts):
    return analyze(ts, strong, system_prompt=cloud_sp)
def coach_runner(qt, ts, patterns):
    return _coach.coach(qt, ts, patterns, strong, system_prompt=coach_sp)
runners = _practice._build_runners(strong, fast_engine=fast)

console = Console()
stage_timer = StageTimer()
print("Running CONCURRENT analysis (claude, cap 3) over a real transcript…")
t0 = time.perf_counter()
outs = coordinator._analyze(
    real_transcripts=real_transcripts, triaged=triaged, question=q, runners=runners,
    grammar_analyzer=grammar_analyzer, coach=coach_runner, store=None, console=console,
    parallel_safe=True, concurrency=3, stage_timer=stage_timer,
)
wall = time.perf_counter() - t0
block = stage_timer.to_frontmatter(analysis_mode=outs.analysis_mode, analysis_concurrency=3,
                                   analysis_wall_seconds=outs.analysis_wall_seconds)
print(json.dumps(block, indent=2))
print(f"\nMEASURED concurrent analysis wall-clock: {wall:.1f}s  (analysis-group wall {outs.analysis_wall_seconds:.1f}s)")
print(f"phase={outs.phase} grammar_patterns={len(outs.grammar_patterns)} coverage_records={len(outs.coverage_records)} "
      f"coaching={'yes' if outs.coaching else 'no'} mishearings={len(outs.pronunciation_flags)}")
Path(__file__).with_name("after_timings.json").write_text(json.dumps({"wall": round(wall,1), "block": block}, indent=2))
