"""Phase-0 empirical measurement: TTS (cold load / pure synth / warm cache) + ASR.

Run: uv run python specs/012-responsive-session-flow/research/measure_tts_asr.py
No network, no claude. Uses the real local Kokoro + Whisper engines + fixture audio.
"""
from __future__ import annotations
import time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

def t():
    return time.perf_counter()

def section(name):
    print(f"\n=== {name} ===")

# Representative static text: first question + ideal answer from the repo default.
from speakloop.content import load
from speakloop.config import paths
qa = load(paths.resolve_qa_file())
q = qa.questions[0]
qtext = q.question.strip()
atext = q.ideal_answer.strip()
print(f"question id={q.id}  q_chars={len(qtext)}  ideal_chars={len(atext)}")

section("TTS — Kokoro")
from speakloop.tts.kokoro_engine import KokoroEngine
from speakloop.tts import cache
eng = KokoroEngine(speed=0.85)

# Unique text to force cache miss + first call also pays lazy model load.
uniq1 = qtext + " [m1-cold-load probe sentinel alpha]"
s = t(); p1 = eng.synthesize(uniq1, voice=q.voice_override); cold_load_plus_synth = t() - s
print(f"first synthesize (lazy model load + synth of ~{len(uniq1)} chars): {cold_load_plus_synth:.3f}s")

# Warm model, cold cache: another unique text → pure synth time only.
uniq2 = atext + " [m2-warm-synth probe sentinel beta]"
s = t(); p2 = eng.synthesize(uniq2, voice=q.voice_override); warm_synth_ideal = t() - s
print(f"warm-model synth of IDEAL-ANSWER-sized text (~{len(uniq2)} chars): {warm_synth_ideal:.3f}s")

uniq3 = qtext + " [m3-warm-synth-q probe sentinel gamma]"
s = t(); p3 = eng.synthesize(uniq3, voice=q.voice_override); warm_synth_q = t() - s
print(f"warm-model synth of QUESTION-sized text (~{len(uniq3)} chars): {warm_synth_q:.3f}s")

# Warm cache: re-synthesize uniq1 → pure cache hit (file lookup).
s = t(); _ = eng.synthesize(uniq1, voice=q.voice_override); warm_cache = t() - s
print(f"warm-CACHE hit (same text again): {warm_cache*1000:.2f}ms")

# Streaming probe: time-to-first-chunk vs whole synth, on the ideal answer.
section("TTS — streaming (generate_stream) time-to-first-audio")
tts = eng._load()
s = t()
it = tts.generate_stream(uniq2[:600], voice=q.voice_override or "af_heart", speed=0.85)
first = next(it)
ttfa = t() - s
nchunks = 1
for _ in it:
    nchunks += 1
total_stream = t() - s
print(f"time-to-first-chunk: {ttfa:.3f}s   total stream ({nchunks} chunks): {total_stream:.3f}s")

# Clean the sentinel cache entries we created so we don't pollute the real cache.
for txt in (uniq1, uniq2, uniq3):
    cp = cache.cache_path(q.voice_override, txt, 0.85)
    if cp.exists():
        cp.unlink()

section("ASR — Whisper")
from speakloop.asr import build_engine
sel = build_engine("whisper")
asr = sel.engine
print(f"engine={sel.engine_name} model={sel.model_id} fell_back={sel.fell_back}")
fix = ROOT / "tests/fixtures/wav/recordings/attempt-3s.wav"
# First transcribe pays the lazy model load.
s = t(); tr1 = asr.transcribe(fix); cold = t() - s
print(f"first transcribe of attempt-3s.wav (lazy load + decode): {cold:.3f}s  -> {tr1.text[:60]!r}")
s = t(); tr2 = asr.transcribe(fix); warm = t() - s
print(f"warm transcribe of attempt-3s.wav (decode only): {warm:.3f}s")

print("\n=== DONE TTS/ASR ===")
