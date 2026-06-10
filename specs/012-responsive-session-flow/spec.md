# Feature Specification: Responsive, Transparent & Faster Practice Session

**Feature Branch**: `012-responsive-session-flow`

**Created**: 2026-06-10

**Status**: Draft

**Input**: User description: "Improve the SpeakLoop practice session along two axes: responsiveness/transparency of the interaction (UX) and execution speed (without any quality trade)."

## Overview

A practice session today runs: warm-up → spoken question + ideal answer → three timed
attempts (4/3/2 min) → spoken follow-ups → full post-session analysis (grammar, coverage,
mishearing, consistency, coaching). Two problems hurt daily use:

1. **Opaque waits.** Engine loads, transcription gaps, and multi-minute post-session
   analysis leave the terminal silent with no labeled state. Text-to-speech (TTS) playback
   cannot be interrupted, so the learner is forced to listen to the whole question and
   whole ideal answer every time, even on repeat reviews.
2. **Ambiguous interaction state.** The learner often cannot tell whether the app is
   playing audio, listening, recording, or processing — especially around the follow-ups,
   where the prompt plays and recording starts with no clear cue.

This feature re-engineers the session **flow** (not its analysis logic, prompts, or models)
to be transparent and controllable, and makes it measurably faster on the stages that the
measurement shows actually dominate — never trading analysis quality for speed.

## Clarifications

### Session 2026-06-10

(Resolved autonomously, optimizing for minimal waiting and an unmistakable recording state.)

- Q: Which single keys drive skip / replay / end-recording / skip-follow-up, and how are they
  surfaced? → A: A small context-aware set, always shown in a one-line hint that lists ONLY the
  keys valid in the current state. `space` = the primary "advance" action of the current state
  (skip the clip that is playing; stop the active recording when done speaking). `r` = replay the
  current/just-played clip (playback states only). `s` = skip the ENTIRE current follow-up
  (follow-up states only — both while its prompt plays and while awaiting its answer). `q` = quit
  (only where quitting already exists, e.g. the listen loop). `Enter` stays an accepted alias for
  `space` so the line-based fallback and piped/non-raw terminals keep working. Reuses existing
  muscle memory (space already advances, r already replays in the listen loop).
- Q: How are the recording indicator and countdown rendered within the existing rich-based
  terminal output? → A: Reuse `rich` (already a dependency) — render exactly one transient state
  region at a time. Recording shows a distinct `● REC` red marker plus a live elapsed/budget
  readout and a remaining-time bar, visually distinct from the playing / transcribing / analyzing
  spinners. The pre-recording countdown renders as a brief transient `Recording in 3 · 2 · 1`
  immediately followed by the `● REC` region. No new dependency.
- Q: Should autoplay of the ideal answer default on or off? → A: Default **on**
  (`autoplay_ideal_answer: true`). Instant skippability already removes the forced-wait cost, so
  default-on keeps the pedagogical value on first review, while a one-line loop.yaml opt-out
  (`autoplay_ideal_answer: false`) suits rapid repeat drills. Preserves today's behavior for
  existing users.
- Q: What is the concurrency cap for parallel-safe analysis calls? → A: Default **3**,
  configurable via loop.yaml `analysis_concurrency` (clamped ≥ 1). Small enough to avoid
  subscription rate-limit / local-resource pressure from concurrent `claude` subprocesses, large
  enough to cover the real fan-out of the independent post-grammar calls. The local in-process
  engine ignores it and stays strictly serial.
- Q: Is the pre-recording countdown audible or visual, and how long? → A: **Visual-only**, ~1.5 s
  total (~0.5 s per tick), no TTS. An audible countdown would add synthesis/playback latency
  before every recording and blow the minimal-waiting and ≤ 12 s-to-first-follow-up budgets. A
  fixed brief visual cue is the decision (no configurable length in scope).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Always know the state, and control it with one key (Priority: P1)

A learner runs a practice session. At every moment, the terminal shows exactly one
unambiguous state — **playing**, **recording**, **transcribing**, or **analyzing** — and
the learner can act on it immediately with a single keypress: skip the question or ideal
answer that is playing, replay it, end a recording the moment they finish speaking, or skip
a follow-up they do not want to answer. Before every recording (attempts *and* follow-ups),
a short "3-2-1, recording" countdown tells them exactly when to start talking, and while
recording, a distinct indicator plus a live elapsed-vs-budget timer is on screen the whole
time. Nowhere does the screen sit silent for more than ~2 seconds without a labeled progress
state.

**Why this priority**: This is the daily-use pain. Without it, the learner wastes time
re-listening to audio they already know, talks into dead air not knowing if the mic is live,
and stares at a black screen during analysis unsure whether the app hung. It delivers value
on its own — even with no speed change, the session becomes legible and controllable.

**Independent Test**: Drive a full session with a fake keyboard and fake audio/clock; assert
that (a) each stage announces exactly one state, (b) each control key produces its effect
(skip stops playback, replay restarts it, early-stop ends recording, skip-followup advances),
(c) a countdown is emitted before every recording, and (d) a recording indicator is present
for the whole recording window. No real microphone, speaker, or keyboard is touched.

**Acceptance Scenarios**:

1. **Given** the question is playing, **When** the learner presses the skip key, **Then**
   playback stops promptly (≤ 500 ms) and the session advances to the next stage.
2. **Given** the ideal answer is playing, **When** the learner presses the replay key,
   **Then** the ideal answer restarts from the beginning.
3. **Given** an attempt recording is about to start, **When** the stage begins, **Then** a
   "3-2-1, recording" countdown is shown, then a recording indicator with a live
   elapsed/budget timer appears and remains for the entire recording.
4. **Given** a recording is in progress and the learner has finished speaking, **When** they
   press the end-recording key, **Then** recording stops and transcription begins under a
   labeled "transcribing" state.
5. **Given** a follow-up question is playing or about to be asked, **When** the learner
   presses the skip-followup key, **Then** that follow-up is abandoned and the session moves
   on without recording an answer.
6. **Given** a non-skippable stage (e.g. mid-transcription) is active, **When** the learner
   presses any control key, **Then** the keypress is ignored gracefully and the session never
   crashes.
7. **Given** the terminal does not support raw single-key input, **When** the session runs,
   **Then** it falls back to the existing line-based control behavior without error.

---

### User Story 2 - Never forced to re-listen; the session closes with a usable summary (Priority: P1)

On repeat reviews of a question the learner already knows, they should not be forced to sit
through the ideal answer again. The ideal-answer playback is instantly skippable, and a
loop-config toggle lets them turn off its autoplay entirely for repeat reviews. When the
session finishes, the terminal prints a compact summary — grade, coverage first→final, the
single top fix, and the next due date — so reading the full report file is optional.

**Why this priority**: Closes the "forced re-listen" complaint and removes the need to open a
Markdown file to learn the one thing that matters (what to fix, when to return). It is
independently testable and shippable alongside US1.

**Independent Test**: With autoplay disabled in config, assert the ideal answer is not played
automatically but can still be replayed on demand; run a session to completion and assert the
end-of-session summary contains grade, coverage first→final, top fix, and next due date,
sourced from the same data written to the report.

**Acceptance Scenarios**:

1. **Given** the autoplay-ideal-answer toggle is off, **When** a session starts, **Then** the
   question plays but the ideal answer is not auto-played; the learner can still trigger it
   with the replay key.
2. **Given** the autoplay toggle is on (default), **When** a session starts, **Then**
   behavior matches today (question then ideal answer auto-play), but the ideal answer is
   skippable mid-stream.
3. **Given** a session completes with analysis, **When** the report is written, **Then** the
   terminal also prints a compact summary line/box with grade, coverage first→final, top fix,
   and next due date.
4. **Given** a session completes in a degraded state (analysis pending), **When** the summary
   prints, **Then** it shows what is available and clearly notes analysis is pending rather
   than fabricating a grade.

---

### User Story 3 - The session is faster, with the analysis quality untouched (Priority: P2)

The learner's wall-clock waiting time shrinks: a warm TTS cache makes launch-to-first-audio
near-instant on repeat reviews; the gap between the end of the last attempt and the first
spoken follow-up is short because follow-up generation starts the moment the final
transcription lands; and the multi-minute post-session analysis runs concurrently (for
engines that are safe to parallelize) instead of strictly serially. The report the learner
gets is **byte-for-byte the same** as it would be with the old serial path, given the same
model outputs. The learner can see where time went via a `--timings` flag and an additive
timing record saved in the report.

**Why this priority**: Speed is the second-most-felt pain, but it must be earned by
measurement and must never alter analysis results. It depends on US1's clear states to remain
legible while work overlaps, so it is sequenced after the transparency work.

**Independent Test**: With stubbed engines returning fixed outputs, run the analysis pipeline
twice — once forced serial, once concurrent — and assert the two reports are byte-identical.
Separately, with a fake clock, assert per-stage timings are recorded and that the `--timings`
flag prints them. Force one of several concurrent analysis calls to fail and assert the
others still complete and only that call degrades to `analysis_pending`.

**Acceptance Scenarios**:

1. **Given** a question whose TTS audio is already cached, **When** the session launches,
   **Then** the first audio plays within 5 seconds.
2. **Given** the final attempt has just ended, **When** the session proceeds, **Then** the
   first spoken follow-up begins within 12 seconds.
3. **Given** a concurrency-safe analysis engine, **When** the post-session analysis runs,
   **Then** its wall-clock is at least 40% shorter than the serial baseline, with an
   identical report.
4. **Given** the local in-process model engine, **When** analysis runs, **Then** the calls
   stay serial (no concurrency) and the report is unchanged.
5. **Given** identical fixed model outputs, **When** the report is built via the serial path
   and via the concurrent path, **Then** the two reports are byte-identical.
6. **Given** one concurrent analysis call raises, **When** the pipeline finishes, **Then**
   the other calls' results are present and only the failed dimension is marked pending.
7. **Given** a crash (e.g. Ctrl-C) mid-analysis, **When** the session is interrupted, **Then**
   the recordings and transcripts survive exactly as today and the session is resumable.
8. **Given** `--timings` is passed, **When** the session ends, **Then** a per-stage timing
   breakdown is printed; **and** regardless of the flag, an additive timing record is saved
   in the report frontmatter (schema_version stays 1).

---

### Edge Cases

- **Keypress during a non-skippable stage** (e.g. mid-transcription, mid-analysis): the key
  is consumed and ignored; no crash, no state corruption.
- **Skip pressed at the exact end of playback**: treated as a no-op (the stage was already
  ending); the session advances normally without double-advancing.
- **Early-stopped recording that is near-empty**: the existing short/garbage-answer handling
  applies unchanged (no new failure mode introduced by early-stop).
- **TTS cache invalidation**: when a question's prompt text or ideal-answer text changes, the
  cached audio for the old text is not reused (content-hash keyed); new audio is synthesized
  automatically.
- **TTS cache growth**: the cache cannot grow without bound; old entries are pruned under a
  size cap, and pruning never deletes an entry mid-playback or corrupts a concurrent read.
- **One concurrent analysis call fails while others succeed**: per-call degradation is
  preserved — only the failing dimension becomes `analysis_pending`; the rest are written.
- **Terminal without raw-mode support** (piped stdin, no controlling TTY): single-key control
  degrades to the current line-based fallback; the session still completes.
- **Ctrl-C mid-session**: audio and transcripts are saved (no loss); a finished-attempts
  session still writes its report; an interrupted-before-attempts session aborts cleanly as
  today.
- **Output device changes mid-playback** (e.g. Bluetooth headphones power off): interruptible
  playback must remain at least as resilient as today's blocking playback (same device-loss
  recovery).

## Requirements *(mandatory)*

### Functional Requirements

#### Transparent, controllable flow (US1)

- **FR-001**: The session MUST, at every stage, present exactly one unambiguous state label
  drawn from {playing, recording, transcribing, analyzing}, such that the learner can always
  tell which one is active.
- **FR-002**: The session MUST never leave the terminal with no visible activity for longer
  than ~2 seconds; any operation exceeding that MUST display a labeled, animated progress
  state (spinner/elapsed) until it completes.
- **FR-003**: While recording (attempts and follow-ups), the session MUST show a distinct
  recording indicator (`● REC` red marker) and a live elapsed-vs-budget readout with a
  remaining-time bar for 100% of the recording duration, visually distinct from the playing /
  transcribing / analyzing states. Rendered with `rich` (existing dependency), one transient
  state region at a time.
- **FR-004**: Before every recording (attempts and follow-ups), the session MUST present a
  brief **visual-only** countdown cue (`Recording in 3 · 2 · 1`, ~1.5 s total, ~0.5 s per tick,
  no TTS) immediately followed by the `● REC` region, so the learner knows precisely when to
  begin speaking without adding synthesis latency.
- **FR-005**: The learner MUST be able to skip the currently-playing TTS clip (question or
  ideal answer) with the **`space`** key, taking effect within 500 ms.
- **FR-006**: The learner MUST be able to replay the currently/just-played TTS clip (question
  or ideal answer) with the **`r`** key.
- **FR-007**: The learner MUST be able to end the current recording early with **`space`** (or
  `Enter`) when they have finished speaking, after which transcription begins.
- **FR-008**: The learner MUST be able to skip the entire current follow-up with the **`s`**
  key (valid both while the follow-up prompt plays and while awaiting its answer), abandoning it
  without recording an answer and advancing the session.
- **FR-009**: Existing voice/line-based commands MUST continue to work; single-key controls
  are the added reliable path, not a replacement that breaks scripted/piped use. `Enter` stays
  an accepted alias for `space`.
- **FR-010**: All single-key controls MUST be discoverable via a short on-screen hint that
  names ONLY the keys valid in the current state and their effect at the moment they are
  available.
- **FR-011**: A keypress arriving during a stage where it has no meaning MUST be ignored
  gracefully without crashing or corrupting session state.
- **FR-012**: When the terminal does not support raw single-key input, the session MUST fall
  back to the existing line-based control behavior and still complete.

#### Never forced to re-listen + closing summary (US2)

- **FR-013**: Ideal-answer playback MUST be instantly skippable (per FR-005).
- **FR-014**: A loop-config toggle (`autoplay_ideal_answer`, default **`true`**) MUST allow
  disabling autoplay of the ideal answer; when off, the question still plays automatically, the
  ideal answer does not, and the learner can still replay the ideal answer on demand with `r`.
  Default-on preserves today's behavior (instant skippability removes the forced-wait cost).
- **FR-015**: On session completion, the terminal MUST print a compact summary containing at
  least: grade, coverage first→final, the single top fix, and the next due date — sourced
  from the same data persisted to the report.
- **FR-016**: The closing summary MUST degrade honestly: in a degraded/analysis-pending
  session it shows what is available and states that analysis is pending, never fabricating a
  grade or coverage figure.

#### Speed, measured & quality-preserving (US3)

- **FR-017**: The session MUST instrument a per-stage timing breakdown covering at least:
  engine warm-up/load, per-attempt record, per-attempt transcribe, follow-up generation, and
  each post-session analysis call.
- **FR-018**: A `--timings` flag MUST print the per-stage breakdown at session end; the
  instrumentation overhead MUST be negligible and always-on (the flag only controls display).
- **FR-019**: The per-stage timings MUST be saved as an additive optional report frontmatter
  key; `schema_version` MUST stay 1 and pre-feature reports MUST still parse unchanged.
- **FR-020**: The synthesized TTS audio for static per-question text (question + ideal
  answer) MUST be cached keyed by a content hash, so repeat reviews reuse it without
  re-synthesizing; a text change MUST automatically invalidate the stale entry.
- **FR-021**: The TTS cache MUST enforce a size cap with a prune policy that removes old
  entries without deleting an entry that is currently in use and without corrupting reads.
- **FR-022**: Transcription of attempt N MUST be able to overlap recording of attempt N+1
  (background transcription), while never running two transcription jobs concurrently with
  each other (the ASR engine processes one job at a time).
- **FR-023**: The ASR/VAD engines MUST be pre-loaded/warmed during the initial question/answer
  playback so the first attempt does not pay a cold-load penalty inside the timed window.
- **FR-024**: Follow-up generation MUST start as soon as the final attempt's transcription is
  available, so the gap to the first spoken follow-up is minimized.
- **FR-025**: Independent post-session analysis calls (grammar, coverage, mishearing,
  consistency, coaching) MUST be eligible to run concurrently with a bounded concurrency cap
  (default **3**, configurable via loop.yaml `analysis_concurrency`, clamped ≥ 1), **only** for
  engines declared safe to parallelize; engines that are a single in-process model MUST stay
  strictly serial (and ignore the cap).
- **FR-026**: An engine MUST declare whether it is safe to parallelize; the session MUST honor
  that declaration when choosing serial vs. concurrent analysis.
- **FR-027**: The concurrent analysis path MUST produce a report that is byte-identical to the
  serial path's report given identical model outputs (identical inputs, identical assembly
  order).
- **FR-028**: Per-call degradation MUST stay per-call: a single failed analysis call MUST
  degrade only its own dimension to `analysis_pending` and MUST NOT poison the other calls'
  results.
- **FR-029**: Recordings and transcripts MUST survive a crash mid-analysis exactly as today;
  an interrupted session MUST remain resumable with no audio/transcript loss.
- **FR-030**: TTS playback MAY begin before full synthesis (chunking/streaming) **only if**
  research confirms the engine supports it without quality loss; otherwise this lever is
  dropped and documented. Any such behavior MUST be a guarded capability check with a fallback
  to whole-clip playback, never an unconditional assumption.

#### Cross-cutting constraints

- **FR-031**: This feature MUST NOT change analysis logic, prompts, models, schemas, or report
  semantics. The only report change permitted is the additive timings frontmatter key.
- **FR-032**: This feature MUST NOT add a new third-party dependency unless raw-keypress
  handling genuinely cannot be met with the standard library plus existing dependencies, in
  which case the justification MUST be recorded in research.
- **FR-033**: The default (no-flag) local-engine path MUST remain offline and MUST NOT regress
  in correctness; any reordering/overlap MUST preserve identical outputs.
- **FR-034**: All keyboard, clock, and audio-control interactions MUST be behind injectable
  abstractions so the automated test suite uses fakes and never touches the real microphone,
  speaker, keyboard, or the real analysis binary.

### Key Entities

- **Session state**: the single active interaction state (playing / recording / transcribing
  / analyzing) surfaced to the learner; drives the on-screen indicator and the active
  control-key hints.
- **Control key binding**: a mapping from a single key to an action (skip, replay, end
  recording, skip follow-up) valid in a particular state.
- **Stage timing record**: a per-stage duration breakdown for one session (warm-up, per
  attempt record/transcribe, follow-up generation, each analysis call), printable and saved
  additively in the report.
- **TTS cache entry**: a content-hash-keyed synthesized audio clip for static per-question
  text, subject to a size-capped prune policy.
- **Engine parallel-safety capability**: a declared property of an analysis engine indicating
  whether its calls may run concurrently (subprocess/HTTP engines: yes; single in-process
  model: no).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a warm TTS cache, launch-to-first-audio is ≤ 5 seconds.
- **SC-002**: The gap between the end of the final attempt and the first spoken follow-up is
  ≤ 12 seconds.
- **SC-003**: On concurrency-safe engines, post-session analysis wall-clock is reduced by
  ≥ 40% versus the measured serial baseline. (If model-inference latency makes a specific
  numeric target physically unreachable without degrading quality, the measured floor and the
  reason are documented instead — quality is never traded for the number.)
- **SC-004**: A TTS skip keypress takes effect within 500 ms.
- **SC-005**: A recording indicator is visible for 100% of recording time, in both attempts
  and follow-ups.
- **SC-006**: The serial and concurrent analysis paths produce byte-identical reports in
  equivalence tests with fixed model outputs.
- **SC-007**: No stage leaves the terminal with no labeled activity for more than ~2 seconds.
- **SC-008**: The full automated test suite is green and never touches the real microphone,
  speaker, keyboard, or analysis binary.
- **SC-009**: `schema_version` stays 1; a pre-feature report parses unchanged and a
  no-timings report is byte-identical to today.
- **SC-010**: Zero new third-party dependencies are added (or, if one is unavoidable for
  raw-keypress handling, it is justified in research and is the only one).

## Assumptions

- **Single learner, single terminal session.** No multi-user or networked-UI concerns; the
  TUI runs in one terminal on macOS (the project's target platform).
- **Raw single-key input is achievable with the standard library** (the codebase already uses
  termios/tty/select for cbreak reads), so no new dependency is expected for keypress
  handling. This will be confirmed in research; if false, FR-032's escape clause applies.
- **The TTS clip cache already exists** (content-addressed by voice/text/speed); this feature
  adds the prune policy and confirms/measures the cache win rather than introducing caching.
- **The recorder already supports early-exit via an event**; the new work is wiring a
  single-key control to it and adding the countdown + indicator, not new capture mechanics.
- **The OpenRouter (HTTP) and Claude Code (subprocess) engines are safe to parallelize**; the
  local Qwen engine (single in-process MLX model) is not and stays serial.
- **"Identical report given identical model outputs"** is interpreted at the serialized-bytes
  level: same inputs to each call, same assembly order, same frontmatter/body — only the
  concurrency of execution differs.
- **Baseline/after measurements** use fixture audio plus a small, capped number of real
  analysis calls; the automated suite uses injected fakes exclusively.
- **The follow-up stage remains interactive** (spoken, recorded). "Start generation early"
  means computing the follow-up questions as soon as the final transcript lands, overlapped
  with any remaining background work — not changing what is asked.

## Out of Scope

- GUI or web UI; visual theming or color schemes.
- Any change to analysis logic, prompts, models, or the report schema (beyond the additive
  timings key).
- Changes to question content or the Q&A file format.
- New third-party dependencies (subject to FR-032's narrow escape clause).
