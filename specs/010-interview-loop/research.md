# Phase 0 Research: Interview Loop

All decisions below resolve the open questions in the spec and the planning brief. Each is grounded in
the existing codebase (recon facts cited as `file.py:line`) and the constitution. Format: **Decision /
Rationale / Alternatives considered**.

---

## R1 — Spaced-repetition algorithm (SM-2 variant vs FSRS-lite)

**Decision**: A **lightweight, grade-banded multiplicative interval ladder** — an SM-2-*inspired* scheme
with **no per-card ease factor**. The next interval is a pure function of (previous interval, this
session's Answer-Quality Grade), exactly as pinned in the spec's Key Definitions:

| Grade | Next interval |
|---|---|
| poor | 1 day (reset to base) |
| fair | 2 days |
| good | previous × 2 |
| strong | previous × 2.5 |

Base interval = 1 day; cap = 21 days until mastery; mastery = two consecutive `strong` with zero content
errors, then a single maintenance review at the 30-day ceiling; any later non-`strong` demotes. This is
implemented as ~30 lines of pure arithmetic in `srs/schedule.py` with no learned parameters.

**Rationale**: The grade is a rich, already-computed 4-band signal (coverage-primary, with a grammar+
fluency fallback). SM-2's ease-factor bookkeeping and FSRS's stability/difficulty/retrievability model
both exist to *infer* recall probability from binary right/wrong reviews at scale (thousands of cards,
many users). Here we have one user, tens-to-hundreds of questions, and a direct quality grade — so the
inference machinery is unnecessary. A transparent ladder is testable (deterministic), matches the
constitution's "boring over novel / a stranger can read it in five minutes," and satisfies every
scheduling FR (FR-010..FR-015) and SC-005 exactly.

**Alternatives considered**:
- *Full SM-2 (per-card ease factor, EF adjustments)*: rejected — the EF feedback loop tunes interval
  growth from review history we already summarize in the grade; adds opaque per-card state for no gain
  at this scale.
- *FSRS-lite (stability/difficulty params)*: rejected — needs fitted parameters and a memory model;
  meaningfully more code and concept surface, opaque, and over-engineered for a single-user bank of
  hundreds of cards. Documented here so the choice is not re-litigated later.

---

## R2 — Transcript triage method (hallucination + mishearing)

**Decision**: **Hybrid, heuristic-first.**

1. **Deterministic hallucination filter (always on, offline, pre-analysis)** — `triage/hallucination.py`
   drops a transcript span before any grammar/coverage/metrics work when it matches strong signals:
   - the span overlaps a **VAD silence gap** (no Silero speech region covering it), and/or
   - its segment **`no_speech_prob` ≥ 0.6** or **`avg_logprob` ≤ −1.0** or **`compression_ratio` ≥ 2.4**
     (the same thresholds Whisper already uses internally but currently discards,
     `whisper_mlx_engine.py:39-44`), and/or
   - the span matches the curated **phantom-phrase list** (`triage/phantom_phrases.txt`, e.g. "thank you",
     "I'll see you later", subtitle/subscribe boilerplate — the canonical Whisper silence hallucinations).
2. **LLM-assisted mishearing classification (when a model is available)** — `triage/mishearing.py` asks
   the injected `LLMEngine` to label low-confidence real-speech tokens that are phonetically close to a
   plausible intended word (e.g. "must"→"mouse") as **pronunciation flags**, returned as structured JSON.

The hallucination filter runs **before** grammar analysis, so **no hallucinated text can ever enter
grammar evidence even when the LLM is the analyzer** (satisfies FR-028/SC-003 deterministically and
offline). Mishearing detection is enrichment: when no LLM is available it is simply skipped (the span
stays as real speech), never blocking the report.

**Prerequisite surfaced**: the ASR `Transcript` must carry the per-segment metadata
(`avg_logprob`, `no_speech_prob`, `compression_ratio`) and the VAD regions that the wrapper currently
**discards** (`whisper_mlx_engine.py:220-227`; VAD via `vad.py:98-107`). These are added as **additive
optional** fields on the frozen `Transcript`/`WordTiming` dataclasses (defaults so every existing call
site and the Parakeet path keep working — Parakeet exposes no confidence and "does not hallucinate on
silence," so its spans default to real speech).

**Rationale**: Hallucinations have crisp, cheap, deterministic signals (silence + Whisper's own
decode-guard thresholds + a known-phrase list); doing them in code is precise, fast, offline, and
LLM-independent — which is exactly what the "never let a hallucination reach grammar evidence" guarantee
needs. Mishearings are phonetic+contextual and genuinely need a model, so they ride the existing LLM
layer and degrade gracefully. The codebase already has a *post-hoc* coherence/garble filter
(`feedback/coherence.py`) but it runs **after** grammar analysis on findings; triage must run **before**
so hallucinated text never reaches the analyzer or the metrics.

**Alternatives considered**:
- *Pure LLM triage*: rejected — would let hallucinations through whenever the LLM is down, violating the
  offline hallucination guarantee, and spends tokens on cases heuristics nail.
- *Pure heuristics (incl. mishearings)*: rejected — phonetic mishearing detection without context is
  low-precision; a phonetics dependency would also violate "near-zero new deps." The LLM already in the
  loop does this better.

---

## R3 — Key-point versioning when the ideal answer is edited

**Decision**: Key points are **keyed by `(question_id, ideal_answer_hash)`**, where `ideal_answer_hash`
is `sha256` of the **normalized** ideal-answer text (trim, collapse internal whitespace, NFC) — truncated
for display. On session start: compute the current hash; if it differs from the cached set's hash,
**re-derive** the key points via the LLM and store the new set under the new hash, incrementing a
monotonic, human-facing **`key_points_version`** counter. Every session report records the **key-point
set + the hash/version it was scored against**, so (a) coverage deltas are only ever compared **within
one version** (FR-023), and (b) the store is rebuildable from session files (the latest session per
question yields the current key points). Whitespace-only edits do not change the normalized hash and do
not trigger re-derivation.

**Rationale**: Content-addressing by a normalized hash is the simplest correct change detector and
matches an existing precedent in the codebase — `AsrProvenance.initial_prompt_sha256`
(`frontmatter.py`) already hashes a prompt with stdlib `hashlib`. Recording the version in each report
keeps the comparison-validity rule (FR-023) enforceable from the files alone and keeps the store a pure
cache.

**Alternatives considered**:
- *Exact byte match*: rejected — trivial whitespace edits would needlessly re-derive (an LLM call).
- *Storing key points in the question bank file*: rejected — violates the "never write to the shipped/
  user question bank" rule (spec FR-018, governance review) and the repo-default/clean-bank model.

---

## R4 — Derived-store format (versioned JSON file vs SQLite)

**Decision**: A **single versioned JSON file** under `~/.speakloop/` (e.g. `~/.speakloop/store.json`),
written atomically (temp file + `os.replace`, mirroring `markdown_writer.write_atomic`), carrying a
top-level `store_version`. It holds three sections: the per-question SRS schedule/mastery state, the
key-point cache (keyed by question_id + ideal-answer hash), and the cross-session grammar-pattern
aggregation. It is **fully rebuildable** from `data/sessions/*.md` via `speakloop rebuild`, so it is a
**cache, not a source of truth** and corruption is always recoverable.

**Rationale**:
- **Zero new dependency**: stdlib `json` is already used across `src/` (`openrouter_engine.py`,
  `grammar_analyzer.py`, etc.); `sqlite3` is used **nowhere** in the codebase (recon: grep empty). JSON
  keeps the dependency surface flat.
- **Transparency**: a human-readable file fits the constitution's "explicit over clever, boring over
  novel," is greppable/diffable, and is friendly to the same user who reads YAML reports.
- **Scale**: tens-to-hundreds of questions → a few KB–tens of KB. Rewriting the whole file atomically on
  each update is trivially cheap; there is no concurrency (single-user CLI), so transactions buy nothing.
- **Rebuildability**: because the file is derived, the "simplest option that supports a single rebuild
  command" is the one with the least machinery — a flat JSON document folded from session files.

Note (FR-040 / Constitution): the store is an **internal cache**, *not* user-facing configuration, so
JSON is permitted. Genuinely user-editable config (daily capacity, loop on/off defaults) lives in a
separate small **YAML** file under `~/.speakloop/`.

**Alternatives considered**:
- *SQLite (`sqlite3`, also stdlib)*: rejected — opaque binary, overkill at this scale, gives transactions
  and indexed queries we do not need, and is less inspectable than JSON. Kept in reserve only if the bank
  ever grows by orders of magnitude (it will not for this user).

---

## R5 — First-follow-up latency (~10 s budget)

**Decision**: Hit the ~10 s target with two concrete, low-cost levers, and treat ~10 s as a **goal, not
a gate** (exceeding it is latency, never a failure):

1. **Warm the analysis model during the final attempt.** The learner speaks for up to 120 s on attempt 3
   (`timer.BUDGETS = (240,180,120)`). When attempt-3 recording starts, kick off a background warm of the
   injected LLM (a no-op/tiny generate) so it is resident when the attempt ends. The follow-up call is
   then short-prompt → short-output (1–2 questions, ≤ ~80 tokens).
2. **Reuse the already-transcribed attempts 1 & 2.** Each attempt is transcribed immediately after it
   ends today (`coordinator.py:185`). At attempt-3 end only the attempt-3 clip needs transcription;
   the follow-up prompt is assembled from the three transcripts and generated, then synthesized with the
   already-warm TTS (`KokoroEngine.synthesize` ~1.5 s on M3 after warm-up, `research_tts.md`).

Estimated critical path on M-series: attempt-3 transcription (~3–6 s for ≤2 min via whisper-large-v3-turbo)
+ warm short LLM generation (~2–5 s) + TTS (~1.5 s) ≈ **7–12 s**.

**Streaming transcription is NOT required** and is out of scope: the file-based transcribe of a single
≤2-min clip plus a warm model fits the budget. If real-world measurement misses the target, the
documented contingency (not built now) is to assemble the follow-up from attempts 1–2 plus a partial
attempt-3 transcript; this is recorded so a future task can pick it up without re-deciding.

**Rationale**: The dominant cost is cold model load, which we hide behind the 120 s the learner is already
speaking. No API change to TTS/ASR is needed (the TTS protocol is path-based, no streaming — and we do
not need it). This respects Principle V (no engine changes) and Principle VIII (warm is a background
thread, not a new import site).

**Alternatives considered**:
- *Streaming/first-sentence TTS*: rejected — requires a TTS protocol change (immutable per Principle V)
  for ~1 s of savings we do not need.
- *Pre-generating the follow-up before attempt 3 ends*: rejected — the follow-up must reference attempt-3
  content (spec FR-001), so it cannot be generated before that attempt completes.

---

## R6 — Reusing the LLM routing layer for all new calls (no new client paths)

**Decision**: Every new language-model step calls the **injected `LLMEngine.generate(system_prompt,
user_prompt, max_tokens, temperature, retry)`** (`interface.py:15-30`) — never an engine package. The
existing `--cloud` flag (`practice.py:231`) selects local Qwen vs OpenRouter exactly as today; the
engine is constructed **once** per session and **reused** across all calls (the pattern already used for
grammar + coach, `_build_cloud_grammar_analyzer` `practice.py:461-512`). `cli/practice.py` is generalized
to build a **bundle of runner closures** (grammar, coach, follow-ups, key-points, coverage, content-
errors, mishearing, consistency, drill) over that single engine, passed into the coordinator by
dependency injection like `grammar_analyzer`/`coach` are now.

Each new call gets: its **own seeded, user-editable prompt file** under `~/.speakloop/` (mirroring
`openrouter_prompt.txt` / `openrouter_coach_prompt.txt` via `cloud_prompt.load_*`), its **own
`MAX_TOKENS` constant**, an **explicit JSON output schema** validated through the **existing recovery
ladder** (`grammar_analyzer._extract_json`: strict → first-`{...}` → `json_repair` → `json_repair`
region; reuse it, do **not** hand-roll regex), and it **raises `LLMEngineError`** on empty/failed
response so the coordinator's existing try/except converts it to a non-fatal `*_error` note.

Temperature intent per call (call site passes temperature only; the engine owns sampler/stop/penalty/
thinking-mode): grammar 0.3 and coach 0.4 already exist; **new analytic calls use 0.2–0.3** (follow-ups
0.4 for natural phrasing). `retry` stays a boolean intent.

**Rationale**: This is the spec's hard constraint (FR-039) and Principle V. The coach (009) is the exact
template for "a second sequential call over the same engine, own prompt file, body-only or additive
output." Reusing `_extract_json` gives every call the same battle-tested JSON resilience for free.

**Alternatives considered**:
- *A new generic "LLM task" abstraction/framework*: rejected — over-abstraction; the codebase prefers
  explicit per-call modules (grammar, coach) over a framework. Each new call is a small module that
  builds a prompt and validates JSON.

---

## R7 — Report `schema_version` discipline for the new fields

**Decision**: Keep the **report `schema_version` at `1`**. Every new per-session datum (question `type`,
warm-up result, follow-ups, per-attempt coverage, content errors, pronunciation flags, answer-quality
grade, key-point set + version, `analysis_pending`) is an **additive optional** frontmatter key emitted
only when present — exactly the discipline 002/003/009 used (`ideal_answer`, `asr`, `coach_error` etc.,
`frontmatter.py:199-212`). Old reports parse unchanged (unknown keys ignored, missing keys default), so
SC-012 holds. The new **store** carries its own independent **`store_version`**.

This reconciles the planning brief's "bump it if fields change" with the codebase reality: in this
codebase additive-optional keys are *non-breaking* (the parser ignores unknown keys and defaults missing
ones), so they do not require a bump. A `schema_version` bump (to 2) is reserved for a genuinely
**breaking** change to an existing field's meaning/shape — and the parser already branches on
`schema_version`, so version-aware reading is in place if that day comes.

**Rationale**: Bumping now would, per the constitution, demand a migration note and would break the
trends reader's version filter for no benefit, since nothing existing changes shape. Matching the
established additive precedent keeps every old report and the trends pipeline working.

**Alternatives considered**:
- *Bump to schema_version 2 on any new field*: rejected — contradicts the 002/003/009 precedent and
  SC-012, and triggers migration machinery for purely additive data.

---

## R8 — Computing fluency metrics over real-speech spans only

**Decision**: `metrics.compute_all(transcript, *, vad_regions=None)` gains an **optional** `vad_regions`
parameter. When triage supplies real-speech regions, speech-rate, pause, filler, and self-correction
metrics are computed over **real-speech spans only** (hallucinated/silence spans removed first); when
`vad_regions is None`, behavior is **byte-identical to today** (denominator = full `audio_duration_seconds`,
word list unfiltered — `speech_rate.py:17-23`, `pauses.py:20-33`). This keeps P4 enrichment additive and
preserves pre-P4 / Parakeet behavior.

**Rationale**: Hallucinated text must affect no metric (FR-025). Threading optional VAD regions keeps the
change additive and the non-triage path unchanged, honoring back-compat and the cached-fixture tests.

**Alternatives considered**:
- *Always recompute over VAD regions*: rejected — would change existing metric outputs for sessions
  without triage and break the Parakeet path (no VAD), violating back-compat.

---

## R9 — Dependency budget

**Decision**: **Zero new third-party dependencies.** New code uses stdlib `json` (store I/O), `hashlib`
(ideal-answer + prompt hashing), `dataclasses`, `datetime` (scheduling), and the **existing** engines/
wrappers. Data files (`phantom_phrases.txt`, the new default prompt files) are packaged text read via
`Path(__file__).parent`, exactly like `feedback/common_words.txt` and the existing default prompts.

**Rationale**: The constitution's "standard library over dependencies" plus the planning brief's
"near-zero new deps." Every capability needed (hashing, JSON, date math, interval arithmetic) is stdlib;
the LLM/ASR/TTS work reuses existing wrappers.

**Alternatives considered**: a phonetics library for mishearings (rejected — LLM handles it, R2); a SRS
library (rejected — 30 lines of arithmetic, R1); an SQLite/ORM layer (rejected — R4).

---

## Cross-cutting confirmations (from recon, no open questions)

- **CLI surface** (`cli/main.py` typer app, lazy command imports): add `today` (due queue, FR-012),
  `rebuild` (store rebuild), `resume` (re-analyze analysis-pending sessions, FR-035a); **extend** the
  existing `trends` command with per-pattern occurrence series (the FR-009 "stats" view — one command,
  not a duplicate); add `--no-warmup`/`--no-followups` to `practice` (FR-007a) and due-based selection
  when no question id is given. New commands keep engine imports function-local (`--help` stays offline).
- **Coordinator insertion points** (`sessions/coordinator.py`): warm-up before the `for ordinal in (1,2,3)`
  loop (a `_do_attempt(ordinal=0,...)`-style stage, stored as `Session.warmup`, not in `attempts`);
  follow-ups after the loop (stored as `Session.follow_ups`, not in `attempts`); triage runs before
  `grammar_analyzer`; coverage per attempt; grade + schedule update + store write after the report is
  written. Abort/early-exit handling and the `phase=='C'`-gates-coach contract are preserved.
- **Graceful degradation** (FR-035): if any analytic call raises `LLMEngineError`, the coordinator's
  existing try/except records a non-fatal note and writes the deterministic report; a new
  `analysis_pending` frontmatter flag marks sessions that need `resume`. The recording is always saved
  first (scratch WAVs are written before analysis, `coordinator.py:166-191`).
- **Labeled validation sets** (SC-003/004/006): extend `tests/fixtures/transcripts/gold_set.yaml` and add
  `tests/fixtures/triage/` + `tests/fixtures/coverage/` with human-authored labels, built from real prior
  sessions independently of the implementation (spec Assumptions — Validation sets).
