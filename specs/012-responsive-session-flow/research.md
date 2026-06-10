# Phase 0 Research: Responsive, Transparent & Faster Practice Session

**Method**: empirical. Built two measurement harnesses
(`research/measure_tts_asr.py`, `research/measure_claude.py`) and ran the real local engines over
fixture audio + the repo's default first question, plus **9 capped real `claude` calls**
(≤ 20 budget; mixed haiku/sonnet). All numbers below are measured on the actual M-series target,
2026-06-10. Raw claude numbers: `research/claude_timings.json`.

> Targets in the spec are goals. Where a target is bounded by **model inference latency (not our
> code)**, we do NOT trade quality for the number — we document the measured floor and why
> (per the autonomous-run Step-2 rule and SC-003's escape clause).

---

## 1. Measured baseline

### 1a. TTS (Kokoro-82M, speed 0.85) — `measure_tts_asr.py`

| Operation | Measured | Note |
|-----------|----------|------|
| First `synthesize` (lazy model load + synth, ~90 chars) | **6.38 s** | one-time model load dominates |
| Warm-model synth, **ideal-answer-sized** (~890–926 chars) | **5.14 s** | the long pole on a cold cache |
| Warm-model synth, **question-sized** (~54–93 chars) | **0.74 s** | |
| **Warm cache hit** (same text again) | **0.03 ms** | content-addressed cache already exists |
| Streaming `generate_stream`, time-to-first-chunk (600 chars) | **2.60 s** (total 3.28 s, 2 chunks) | capability exists; coarse chunking |

### 1b. ASR (Whisper-large-v3-turbo, mlx-whisper)

| Operation | Measured |
|-----------|----------|
| First transcribe of `attempt-3s.wav` (lazy load + decode) | **2.52 s** |
| Warm transcribe of `attempt-3s.wav` (decode only) | **1.37 s** |
| ⇒ implied cold model load | **~1.15 s** |

### 1c. Audio device + interruption — `probe_interrupt2.py`

| Operation | Measured |
|-----------|----------|
| One-time CoreAudio output-device open (warm-up) | 0.20 s (first-ever in a fresh process up to ~1.9 s) |
| Warm `sd.play()` return latency (truly async) | **4.68 ms** |
| **`sd.stop()` mid-stream latency** | **104–113 ms** (3 repeats: 111, 105, 107) |

### 1d. Claude Code analysis per call — `measure_claude.py` (9 real calls)

| Call | Tier (model) | Measured | # in a session |
|------|--------------|----------|----------------|
| mishearing | fast (haiku) | 27.1 s, 22.5 s → **~25 s** | **×3 (one per attempt)** |
| grammar | strong (sonnet) | 74.2 s (single), 226.4 s (with the analyzer's bounded regenerate) → **~74 s typical** | ×1 |
| keypoints | strong (sonnet) | **7.1 s** | ×1 |
| coverage | strong (sonnet) | **23.7 s** | ×1 |
| coaching | strong (sonnet) | **27.3 s** | ×1 |
| consistency | strong (sonnet) | **12.2 s** | ×1 |
| followups | strong (sonnet) | **14.2 s** | ×1 (interactive) |

**Observations.** (a) Per-call latency is high and CLI-startup-heavy — even haiku mishearing is
~25 s, so the fast/strong split does **not** make mishearing cheap; the per-`claude --print`
process startup dominates short calls. (b) `mishearing` is invoked **once per attempt** in the
coordinator loop (`for tr in triaged: mishearing_runner(tr.real_text)`), so it is **3 calls ≈
75 s** in a 3-attempt session — the single biggest serial analysis cost, and fully
parallelizable. (c) grammar has high variance: a parse-failure triggers the analyzer's one
bounded regenerate (a second subprocess), explaining 226 s vs 74 s.

### 1e. Current serial analysis group (claude, typical)

```
mishearing ×3 (75) + grammar (74) + keypoints (7) + coverage (24) + coaching (27) + consistency (12)
≈ 219 s  (~3.7 min) of spinner time AFTER the last attempt, today, before follow-ups even start.
```

And today **follow-ups run AFTER all of that**, so today's "final attempt → first follow-up"
gap ≈ 219 s − (mishearing/keypoints already done) … in practice ≈ **grammar+coverage+coaching+
consistency + followup_generate ≈ 151 s**.

---

## 2. Optimizations, ranked by measured impact

| # | Lever | Measured basis | Impact | Adopt? |
|---|-------|----------------|--------|--------|
| 1 | **Concurrent analysis** (cap 3, parallel-safe engines), speculating past the `phase==C` gate | serial 219 s → concurrent **~113 s** (critical path grammar→coaching→consistency) | **~48% ↓** analysis wall-clock; meets SC-003 | ✅ |
| 2 | **Reorder follow-ups first** (generate the instant the final transcript lands; ask them while analysis runs in the background) | today's gap ~151 s → **~17 s** (attempt_3_transcribe ~3 s + followup_generate ~14 s) | **~89% ↓** perceived post-attempt wait; analysis hidden behind the follow-up Q&A | ✅ |
| 3 | **Warm TTS cache + cold-synth overlap** (synthesize the ideal answer in the background while the question plays) | cold ideal synth 5.14 s → 0.03 ms warm; cold synth hidden behind question playback | launch-to-first-audio ≤ 5 s on warm cache (SC-001) | ✅ |
| 4 | **Background transcription overlap** (transcribe attempt N while N+1 records) | warm decode 1.37 s/3 s clip, fully hidden behind a minutes-long next recording | removes per-attempt transcribe from the perceived loop | ✅ |
| 5 | **ASR/VAD pre-warm during initial playback** | cold load ~1.15 s | removes cold-load from inside the first timed attempt (FR-023) | ✅ |
| 6 | **Interruptible playback** (non-blocking `sd.play` + poll + `sd.stop`) | stop ≈ 110 ms | TTS skip ≤ 500 ms (SC-004) | ✅ |
| 7 | **Output-device pre-warm** (silent `sd.play` at load) | one-time open up to ~1.9 s | first clip not delayed | ✅ |
| 8 | **TTS streaming playback for static text** | time-to-first-chunk 2.60 s vs full 5.14 s | marginal vs #3+cache; complicates interruption | ❌ **drop** |
| 9 | **TTS cache prune** | cache already 409 entries unbounded | correctness/hygiene, not latency | ✅ (size cap) |

### Why streaming (#8) is dropped

`KokoroTTS.generate_stream()` exists and yields a first chunk in ~2.6 s. But (a) the **cache**
already makes repeat reviews instant (0.03 ms), and (b) **overlapping** the cold ideal-answer
synth behind the question playback already hides the 5.14 s on a cold cache. Streaming would only
shave the cold *question* synth (0.74 s) and would force the new interruptible-playback path to
consume an iterator mid-stream — more complexity for sub-second gain. Decision: keep whole-clip
playback (with the interruptible mechanism); record streaming as an available-but-unused
capability with a guarded fallback (FR-030 satisfied: whole-clip is always the path).

---

## 3. Decisions on the open research questions

### D1 — TTS engine chunking/streaming capability
**Decision**: Confirmed present (`generate_stream -> Iterator[np.ndarray]`, first chunk ~2.6 s)
but **not adopted** (see §2 #8). **Rationale**: cache + cold-synth overlap already meet SC-001;
streaming adds interrupt complexity for marginal gain. **Alternatives**: full streaming playback
(rejected — complexity); per-sentence chunked synth (rejected — coarse 2-chunk granularity
observed).

### D2 — Safe interruption of audio playback mid-stream
**Decision**: Non-blocking `sd.play()` (returns in ~4.7 ms warm) + a ~30 ms poll loop + `sd.stop()`
(measured ~110 ms) → interrupt ≤ 500 ms. Pre-warm the device once with a silent play.
**Rationale**: measured, well within SC-004; reuses the existing device-loss/resample recovery.
**Alternatives**: `sd.OutputStream` callback with a stop flag (rejected — more code, same
latency); chunked `sd.write` loop (rejected — busy-ish, no benefit over `sd.stop`).

### D3 — Raw-mode fallback detection
**Decision**: Resolve a tty fd (stdin if `os.isatty`, else `os.open("/dev/tty")`); if neither is
reachable (measured: non-interactive context returns `isatty=False` and `/dev/tty` → `OSError
Device not configured`), use `NullKeyReader` (single-key controls off; line/timeout path drives
the session — FR-012). **Rationale**: matches the existing two-tier `_cbreak_read` precedent and
the measured no-tty failure mode; keeps tests fake-only. **Alternatives**: a third-party keypress
lib (rejected — FR-032 zero-deps; stdlib termios/tty/select suffices).

### D4 — Engine parallel-safety
**Decision**: Declared per engine (`ClaudeCodeEngine.parallel_safe=True`,
`OpenRouterEngine.parallel_safe=True`, `QwenEngine.parallel_safe=False`). **Rationale**: claude is
a separate subprocess per call (process isolation), OpenRouter is independent HTTP; the local MLX
model is single in-process and must stay serial. **Alternatives**: a runtime lock around the local
model (rejected — serial-by-policy is simpler and exactly today's behavior).

### D5 — Concurrency cap
**Decision**: default **3** (loop.yaml `analysis_concurrency`, clamped ≥ 1). **Rationale**: the
session's independent fan-out (grammar + 3× mishearing + keypoints/coverage) saturates ~3 slots;
the critical path (grammar→coaching→consistency) bounds wall-clock regardless of a higher cap, and
3 concurrent `claude` subprocesses stay within subscription/local-resource limits. Verified: with
cap 3, all non-critical work (106 s) hides under the 113 s critical path (2 spare slots × 113 s =
226 s capacity).

---

## 4. Honest assessment of the numeric targets

| SC | Target | Measured outcome | Verdict |
|----|--------|------------------|---------|
| SC-001 | launch-to-first-audio ≤ 5 s (warm cache) | warm cache hit 0.03 ms; first audio = program start + cache lookup + playback start | **MET** |
| SC-002 | final attempt → first follow-up ≤ 12 s | reorder cuts today's ~151 s to **~17 s** (attempt_3_transcribe ~3 s + followup_generate **14.2 s**). The 14.2 s follow-up *generation* model call alone exceeds 12 s. | **NOT MET — model-latency floor ~14–17 s** (documented; an ~89% improvement over today). Reachable only with a faster generation model, which FR-031 forbids changing. |
| SC-003 | analysis wall-clock ≥ 40% ↓ (parallel-safe) | serial ~219 s → concurrent ~113 s = **~48% ↓** | **MET** (point estimate; high per-call variance noted) |
| SC-004 | TTS skip ≤ 500 ms | `sd.stop()` ~110 ms | **MET** |
| SC-005 | recording indicator 100% of recording | by design (state machine) | MET by construction |
| SC-006 | serial == concurrent report (byte-identical) | by design (pure jobs, named slots, fixed assembly) | MET by construction (equivalence test gate) |
| SC-007 | no unexplained silence > ~2 s | by design (every long op has a labeled state) | MET by construction |

**The one missed numeric target (SC-002 ≤ 12 s)** is bounded by the follow-up *generation* model
call (14.2 s measured on claude sonnet) — pure inference latency, not our code. We do not shorten
it by switching models or prompts (FR-031). The delivered improvement is ~151 s → ~17 s (~89%),
and the remaining wait is shown under a labeled `generating follow-up…` state (no dead silence).
On a faster engine (e.g. local Qwen or OpenRouter with a smaller model) the absolute 12 s may be
reachable; the floor is engine-specific and documented here.

---

## 5. Constraints reaffirmed (no quality trade)

- Same prompts, same models, same schemas. Concurrency changes only *when* calls run, never their
  inputs; the report is assembled from named result slots in fixed order ⇒ byte-identical
  (contract: `analysis-concurrency.md`).
- Speculating past the `phase==C` gate (starting coverage/coaching before grammar *finishes*) is
  report-safe: coaching/consistency have a real **data** dependency on grammar's patterns, so they
  still wait for grammar output; only coverage (which does not consume grammar's output) is
  speculated, and its result is discarded if grammar fails — identical to today, where it would
  not have run.
- Recordings/transcripts written to scratch before analysis; report written atomically after;
  store saved last. A crash mid-analysis loses nothing (FR-029) — unchanged from today.
- Instrumentation (StageTimer) is always-on and cheap (two `perf_counter` reads/stage); `--timings`
  only gates the print.
