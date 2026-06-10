# Data Model: Responsive, Transparent & Faster Practice Session

This feature is **flow re-engineering**: it adds in-memory orchestration entities and exactly
one additive, optional persisted field. No existing persisted shape changes; `schema_version`
stays **1**.

## Persisted (report frontmatter)

### `Session.timings` — additive optional key (the ONLY persisted change)

A per-session, per-stage wall-clock breakdown. Emitted **only when present** (like every other
010/011 additive key), so a no-timings report is byte-identical to today and a pre-feature
report parses unchanged (`frontmatter.parse` ignores unknown keys, defaults missing ones).

```yaml
timings:
  schema: 1                      # internal shape version of the timings block itself
  total_seconds: 412.7
  stages:                        # ordered; each is one measured stage
    - { name: "tts_warm",            seconds: 0.20 }
    - { name: "listen_synth_question", seconds: 0.00 }   # 0 ≈ cache hit
    - { name: "listen_synth_ideal",  seconds: 0.00 }
    - { name: "asr_warmup",          seconds: 1.10 }
    - { name: "attempt_1_record",    seconds: 95.3 }
    - { name: "attempt_1_transcribe",seconds: 3.4, overlapped: true }
    - { name: "attempt_2_record",    seconds: 88.1 }
    - { name: "attempt_2_transcribe",seconds: 3.1, overlapped: true }
    - { name: "attempt_3_record",    seconds: 61.0 }
    - { name: "attempt_3_transcribe",seconds: 2.9 }
    - { name: "followup_generate",   seconds: 11.2 }
    - { name: "analysis_grammar",    seconds: 22.0 }
    - { name: "analysis_mishearing", seconds: 6.1 }
    - { name: "analysis_keypoints",  seconds: 7.4 }
    - { name: "analysis_coverage",   seconds: 14.0 }
    - { name: "analysis_coaching",   seconds: 18.5 }
    - { name: "analysis_consistency",seconds: 5.0 }
  analysis_wall_seconds: 24.3    # wall-clock of the analysis group (concurrent ≤ sum-of-stages)
  analysis_mode: "concurrent"    # "serial" | "concurrent"
  analysis_concurrency: 3
```

- `stages[].seconds` is wall-clock for that stage. `overlapped: true` marks a stage whose
  wall-clock ran hidden behind another (e.g. attempt-N transcription behind attempt-N+1
  recording) so a reader does not double-count it against `total_seconds`.
- `analysis_wall_seconds` is the measured wall-clock of the post-session analysis group
  (the figure SC-003's ≥ 40% target is computed against); on a concurrency-safe engine it is
  ≤ the sum of the individual `analysis_*` stage seconds.
- `analysis_mode` records whether the analysis ran serially (single in-process model) or
  concurrently (subprocess/HTTP engine), so a report is self-documenting.
- **Validation**: all `seconds` ≥ 0; `name` from a fixed vocabulary; the block is informational
  only — nothing downstream parses it for behavior (trends ignore it). Round to 0.1 s on dump.

### Round-trip rules

- `frontmatter.dump`: append `payload["timings"] = session.timings` only `if session.timings`.
- `frontmatter.parse`: `timings = data.get("timings") if isinstance(..., dict) else None`.
- `report_builder`: timings are **not** rendered into the human Markdown body (kept to
  frontmatter), matching how other machine-only structured keys are handled. `--timings`
  prints them to the terminal at session end (display only).

## In-memory orchestration entities (not persisted)

### `StageTimer` (`feedback/timings.py` or `sessions/stage_timer.py`)

- **Fields**: ordered list of `(name, seconds, overlapped)` records; an injectable
  `clock=time.perf_counter`.
- **Behavior**: `with timer.stage("name", overlapped=False): ...` records the elapsed; a
  manual `start(name)/stop(name)` pair supports background/overlapped stages. `to_frontmatter()
  -> dict` builds the `timings` block above; `render() -> rich.Table` for `--timings`.
- **Always-on**: instrumentation is unconditional and cheap (two `perf_counter` reads per
  stage); the `--timings` flag only gates the terminal print (FR-018).

### `KeyReader` (`sessions/keyboard.py`) — injectable keyboard abstraction

- **Protocol**: `__enter__/__exit__` (enter/exit raw mode), `poll() -> str | None`
  (non-blocking; returns a canonical key name `{"space","enter","r","s","q"}` or `None` if no
  key is waiting). Canonicalization mirrors today's `_cbreak_read` / `_parse_line_command`.
- **`RawKeyReader`**: termios/tty cbreak on a resolved tty fd (stdin if a tty, else
  `/dev/tty`), `select.select(timeout)` poll. The ONLY new raw-input code; consolidates the
  two existing ad-hoc readers (`cli/practice._cbreak_read`, `coordinator._spawn_enter_reader`).
- **`NullKeyReader`** (fallback): when no tty is reachable, `poll()` returns `None` forever and
  the session relies on the existing line-based path / time budgets (FR-012). `__enter__`
  succeeds (no-op) so call sites are uniform.
- **`FakeKeyReader`** (tests only): replays a scripted, timed key sequence; never touches a
  real fd. Every keyboard-driven test injects this (SC-008).

### `SessionState` + state display (`sessions/session_ui.py`)

- **Enum**: `PLAYING | RECORDING | TRANSCRIBING | ANALYZING` — exactly one active at a time
  (FR-001). Each renders a distinct, transient `rich` region:
  - `PLAYING`: `▶ playing <label>… (space=skip · r=replay)` + spinner.
  - `RECORDING`: `● REC <label> — 12s / 120s` red marker + remaining-time bar
    (`space/Enter=stop`); visible 100% of the recording (FR-003, SC-005).
  - `TRANSCRIBING`: `⠋ transcribing…` spinner + elapsed.
  - `ANALYZING`: `⠋ <what>…` spinner + elapsed (the existing `_analyzing` look, generalized).
- **Countdown**: `countdown()` renders a transient `Recording in 3 · 2 · 1` (~0.5 s/tick,
  visual-only) immediately before a `RECORDING` region (FR-004).
- **Control-hint**: each state prints a one-line hint naming ONLY the keys valid right now
  (FR-010). Hints are sourced from the state→keys map so they never drift from behavior.

### `InterruptiblePlayback` (`audio/playback.py`)

- **New fn**: `play_interruptible(wav_path, *, should_stop, on_first_frame=None) -> bool`
  starts a non-blocking `sd.play`, polls `should_stop()` every ~30 ms, calls `sd.stop()` on
  true, returns `interrupted: bool`. Reuses the existing device-loss recovery / resample
  fallback. Measured `sd.stop()` latency ≈ 110 ms ⇒ within SC-004's 500 ms.
- **`warm_output_device()`**: a tiny silent `sd.play` to pay the one-time CoreAudio open up
  front (measured ~0.2–1.9 s) so the first real clip is not delayed (FR-023 sibling).
- The existing blocking `play()` stays for the debrief read-aloud and the line-based fallback.

### `AnalysisPlan` / executor (`sessions/analysis.py`)

- **Job**: a named, pure analysis unit `(name, fn, depends_on)` returning a typed result;
  wrapped so an exception is captured as that job's failure WITHOUT affecting siblings
  (per-call degradation, FR-028).
- **Dependency DAG** (preserves today's gates exactly so the report is identical):
  - `grammar` (root) · `mishearing` (independent)
  - `keypoints → coverage` — runs only if `grammar` succeeded (today's `phase == "C"` gate)
  - `coaching → consistency` — runs only if `grammar` succeeded
  - `followups` (independent of grammar; on the ≤12 s critical path → scheduled first)
- **Two strategies, one result-set**:
  - **serial** (single in-process model / parallel-unsafe): run jobs in a fixed topological
    order on the calling thread (today's order). 
  - **concurrent** (parallel-safe engine): `ThreadPoolExecutor(max_workers=cap)` honoring the
    DAG; collect results into named slots.
  - Both produce the **same result-set**; the report is assembled from that set in a **fixed
    field order**, so the two strategies yield byte-identical reports (FR-027, SC-006).
- **Store mutations are deterministic & main-thread-only**: jobs are pure; the key-point cache
  write and the pattern-series append happen on the calling thread, post-join, in fixed order
  — so concurrency never reorders persisted store state.
- **Parallel-safety source**: the engine declares it (`ClaudeCodeEngine.parallel_safe = True`,
  `OpenRouterEngine.parallel_safe = True`, `QwenEngine.parallel_safe = False`); the CLI reads
  `getattr(engine, "parallel_safe", False)` and passes it (with the cap) into `run_session`.

### `TtsCache` prune (`tts/cache.py`)

- **Existing**: content-addressed `sha256(voice|[speed|]text)` → `<key>.wav`. Hash-keying
  already gives automatic invalidation on text change (FR-020) and instant warm hits (measured
  ~0 ms).
- **New `prune(max_bytes)`**: when the cache directory exceeds the cap, delete least-recently
  used entries (by `st_mtime`/`st_atime`) until under cap. Never deletes the entry just
  stored; tolerant of a concurrent reader (a deleted-then-read race raises the normal
  `PlaybackError`, handled as today). Default cap a few hundred MB (config constant), pruned
  after each `store()`.

## Configuration (`loop.yaml`, additive optional keys)

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `autoplay_ideal_answer` | bool | `true` | When false, the ideal answer is not auto-played (still replayable with `r`). FR-014. |
| `analysis_concurrency` | int | `3` | Max concurrent analysis calls on a parallel-safe engine; clamped ≥ 1; ignored by the local engine. FR-025. |

Both follow the existing `LoopConfig` pattern (absent/invalid file → defaults; no auto-create).

## Invariants preserved

- `schema_version` stays **1**; `timings` is additive optional; no existing key changes shape.
- Session files remain the source of truth; recordings/transcripts survive a mid-analysis crash
  exactly as today (scratch `attempt-*.wav` written before analysis; abort cleanup unchanged).
- The default local path stays offline and byte-identical in report output.
