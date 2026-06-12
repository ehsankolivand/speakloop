# Feature Specification: Pronunciation Trainer (hear → say → see → retry)

**Feature Branch**: `017-pronunciation-trainer`

**Created**: 2026-06-12

**Status**: Draft

**Input**: User description: "Make the read-aloud pronunciation feature from 016 actually useful as a genuine *hear → say → see → retry* trainer: play the correct pronunciation first (local TTS), let the learner replay it, give an immediate bounded retry when a sound is off, practice full sentences (not just words), focus on the sounds the learner keeps missing, and make it usable as a focused standalone activity (a `pronounce` command) — not only as filler during the interview-feedback wait. Additive: preserve offline-by-default, the safety gate, the honest calibration (detection-led, diagnosis hedged), and the report schema (stays 1)."

## Overview

Feature 016 added an optional read-aloud pronunciation drill block that runs during the
interview-feedback wait: it shows a target word, the learner reads it, and it is scored against the
word's known canonical phonemes with calibrated, segment-level feedback. It is safe and correct, but
it is **not yet a real pronunciation trainer**. It never lets the learner *hear* the correct
pronunciation before speaking; it practises isolated words and minimal pairs rather than natural
sentences; it gives one shot with no immediate retry; and it only runs inside an interview session.

Pronunciation improves through a **tight loop**: *hear* the target, *say* it, *see* exactly what was
off (calibrated, hedged), *hear* it again, *try* again — repeated on the sounds the learner keeps
missing. This feature builds that loop and makes it usable on its own.

It is strictly **additive** on top of 016 and the rest of the project:

- It reuses 016's wav2vec2 scorer, pure-numpy GOP, bundled canonical phonemes, and the
  engine/RAM safety gate; it reuses the existing local **Kokoro TTS** for the *hear-first* step and
  the existing recorder for capture.
- It changes no grammar/coaching analysis, no report `schema_version` (stays **1**), and no
  offline-by-default guarantee. A session that runs no drills produces a **byte-for-byte identical**
  report to a pre-feature session.
- All new model needs reuse the existing opt-in aria2 consent/download flow; no new download path.

Scoring remains **read-aloud only** (known target text). Scoring spontaneous interview answers,
prosody/stress/intonation, general text-to-pronunciation for arbitrary sentences, and MPS inference
are all explicitly out of scope (see Out of Scope / Future).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hear it, say it, see it, retry it (Priority: P1)

A learner reaches the drill block (during an interview-feedback wait, or in the standalone mode of
US3). Before each drill the tool **plays the target aloud** with the local TTS so the learner hears
the correct pronunciation first; the learner can **replay it on demand**. The learner then reads it
aloud and is scored. When a sound was off, the tool offers an **immediate, bounded retry on the same
item**: hear it again → say it again → see whether it improved. Once the item is clear (or the retry
budget is spent), the loop moves on.

**Why this priority**: This is the pedagogical core — the difference between "read this text" and a
trainer that actually improves pronunciation. Hearing the model pronunciation before speaking and
fixing a sound *while it is fresh* are what make the loop work. Without it, the feature is the 016
status quo.

**Independent Test**: In a drill block with a TTS engine available, confirm: (a) the target is spoken
before the learner is asked to read it; (b) the learner can trigger a replay before recording;
(c) a deliberately mispronounced flagged item triggers a retry offer that re-plays the target and
re-records; (d) the retry result is shown as improved/still-off without blame; (e) the retry count
per item is bounded by the configured limit and never loops unboundedly.

**Acceptance Scenarios**:

1. **Given** a drill block with a TTS engine and playback available, **When** a drill begins, **Then**
   the tool plays the target audio before prompting the learner to read it.
2. **Given** the target has just been played and the terminal is interactive, **When** the learner
   asks to hear it again, **Then** the tool replays the same target audio and still lets the learner
   record when ready.
3. **Given** a drill scored with a flagged sound and the retry budget is not exhausted, **When** the
   item finishes scoring, **Then** the tool offers one more attempt on the **same** item, re-plays the
   target, re-records, and re-scores it.
4. **Given** a retry that now clears the previously-flagged sound, **When** it is scored, **Then** the
   tool reports the improvement encouragingly (e.g. "better — that sound is clear now"); **Given** a
   retry that is still off, **Then** the tool says so calmly and moves on (never blaming, never
   looping past the bounded retry limit).
5. **Given** no TTS engine/playback is available (e.g. a non-interactive or audio-less context),
   **When** a drill begins, **Then** the hear-first and replay steps are silently skipped and the
   drill still records and scores exactly as in 016 (graceful degradation).

---

### User Story 2 - Practise full sentences, not just words (Priority: P2)

The learner practises **natural sentences** as the primary unit — short, useful sentences (several
resembling real technical-interview phrasing) that each exercise a target sound. They both *hear* and
*read* the whole sentence. Isolated minimal-pair words remain available as **targeted follow-ons**
when a specific sound is flagged.

**Why this priority**: Sentence-level practice is closer to real speaking than isolated words, and
it makes the loop feel like genuine practice rather than a flashcard drill. It depends on the
hear-first loop (US1) to be worthwhile.

**Independent Test**: Run the drill block and confirm the base practice items are sentences (multiple
words), that they are both spoken and shown, and that a flagged contrast still routes into
word-level minimal-pair follow-ons. Confirm the build-time correctness harness (see Requirements)
scores every bundled sentence clean.

**Acceptance Scenarios**:

1. **Given** the expanded bundled drill bank, **When** the drill block selects base drills, **Then**
   the base items are natural sentences (more than one word), each tied to a target contrast.
2. **Given** a sentence drill flags a recurring contrast, **When** follow-ons are routed, **Then** the
   tool can present bounded word-level minimal-pair drills for that contrast (the 016 routing).
3. **Given** every bundled drill (sentence or word), **When** the build-time correctness harness
   renders it with the local TTS and scores it, **Then** it scores **clean** (no false flags on the
   target) — a drill whose canonical sequence is wrong fails the harness and must be fixed before
   shipping.

---

### User Story 3 - A focused standalone pronunciation mode (Priority: P3)

The learner runs a dedicated **`speakloop pronounce`** command to practise pronunciation **outside**
an interview session, for as long as they want. It runs the same hear → say → see → retry loop over a
set of drills. Because **no feedback engine is resident** in this mode, the safety gate simplifies to
a **live-memory-only** check, so drills are available in the common case (not blocked by the local
feedback engine the way an interview session is). The command ensures the required local models (the
pronunciation model + the TTS model) are present, using the existing consent/download flow if needed.

**Why this priority**: Pronunciation practice should not be gated behind an interview-feedback wait.
A standalone mode makes it a real, repeatable activity the learner returns to. It builds directly on
US1's loop.

**Independent Test**: Run `speakloop pronounce` with a faked recorder/scorer/TTS and confirm: (a) it
runs the hear → say → see → retry loop; (b) its gate uses the **RAM-only** check (a local feedback
engine being *configured* does not block it, unlike an interview session); (c) it lets the learner
keep practising and ends cleanly on quit with a short summary; (d) it never loads the model when
free memory is below the safe threshold (the same conservative behaviour as 016), with the same
explicit freeze-warned override.

**Acceptance Scenarios**:

1. **Given** the models are present and free memory is sufficient, **When** the learner runs
   `speakloop pronounce`, **Then** the tool runs the hear → say → see → retry loop over drills and
   lets the learner continue or stop at their own pace.
2. **Given** the standalone mode, **When** the safety gate is evaluated, **Then** it considers only
   live available memory (there is no feedback engine to account for) — the interview-session rule
   "local feedback engine ⇒ unsafe" does **not** apply here.
3. **Given** free memory is below the safe threshold, **When** the learner runs `speakloop pronounce`,
   **Then** the tool does not load the model by default, explains why in plain language, and offers
   the same explicit freeze-warned override before proceeding.
4. **Given** the pronunciation model and/or TTS model are absent, **When** the learner runs
   `speakloop pronounce`, **Then** the tool discloses size and asks for consent through the existing
   resilient downloader; declining exits cleanly with a hint, and nothing is downloaded silently.
5. **Given** the learner ends the standalone run, **When** the loop stops, **Then** the tool shows a
   short, encouraging summary (how many drills, which sound was trickiest) and writes no interview
   session report (a standalone run is not an interview session).

---

### User Story 4 - Practise the sounds you actually struggle with (Priority: P4)

Within a run, the tool **prioritises drills for the contrasts the learner is getting wrong**, so a
recurring weakness gets more practice than a sound the learner already says well. As a cross-session
enhancement, the tool keeps a **lightweight per-contrast difficulty tally** so future practice biases
toward the learner's historically weak sounds, and surfaces a short **"your tricky sounds"** summary.
When there is no history, selection **degrades gracefully** to the curated default order.

**Why this priority**: A trainer that keeps drilling sounds the learner already mastered wastes their
time. Focusing on actual weaknesses is what makes repeated practice pay off. It layers on top of the
loop (US1) and the bank (US2) and must never break the no-history path.

**Independent Test**: With a recorded history of a weak contrast, confirm the next run orders base
drills so that weak contrast comes first; with no history, confirm the curated default order is used
unchanged. Confirm the "tricky sounds" summary reflects the flagged contrasts and that a session
which ran no drills is unaffected (byte-identical report).

**Acceptance Scenarios**:

1. **Given** one or more contrasts were flagged earlier in the same run, **When** the tool selects
   subsequent drills, **Then** it biases toward the flagged contrast(s) (the 016 follow-on routing,
   strengthened by an in-run tally).
2. **Given** a persisted cross-session tally with a weak contrast, **When** a new run selects base
   drills, **Then** drills for that contrast are ordered ahead of the rest; **Given** no persisted
   history, **Then** the curated default order is used unchanged.
3. **Given** a run that flagged contrasts, **When** the summary/report renders, **Then** a short
   "tricky sounds" line lists the most-missed contrast(s); **Given** a run with no flags, **Then** no
   such line appears and (for an interview session) the report is unchanged.

---

### User Story 5 - Discoverable docs (Priority: P5)

A learner reading the README/quickstart finds a short section describing the trainer loop and the
`pronounce` command: that the tool plays the target first, lets you retry, practises sentences, and
runs standalone; that it stays opt-in, offline, engine/memory-gated, and read-aloud only; and how to
turn the pieces on/off.

**Why this priority**: Discoverability and correct expectations. Lowest priority because the feature
works without it.

**Independent Test**: Read the README pronunciation section and confirm it documents the hear-first
playback, the bounded retry, sentence practice, the `pronounce` command, and the new config keys
(playback toggle, retry count) plus the unchanged 016 gating.

**Acceptance Scenarios**:

1. **Given** the README, **When** a learner searches for pronunciation, **Then** they find the trainer
   loop, the `pronounce` command, the config keys, and why drills may be skipped on their machine.

---

### Edge Cases

- **No TTS / audio-less context**: hear-first and replay are skipped silently; the drill still
  records and scores (the 016 path). The feature never *requires* playback to function.
- **TTS synthesis fails for one item**: that item's hear-first step is skipped with no error; the
  drill continues (playback is best-effort, never fatal).
- **Silent / not-captured retry**: a retry with no captured speech is reported as "not captured",
  not as a failure, and the loop still advances (the bounded retry budget is consumed or the item is
  left as not-captured — never an infinite re-ask).
- **Retry budget = 0**: when the configured retry count is 0, the loop behaves like 016 (one attempt
  per item, no retry offer).
- **Standalone with a local feedback engine configured**: the standalone gate ignores the configured
  feedback engine (none is resident) and checks only live memory; an interview session in the same
  configuration still skips drills (the 016 rule is unchanged).
- **Standalone, model/TTS download declined**: the command exits cleanly with a one-line hint; no
  partial/silent download.
- **Ctrl-C during the standalone loop or the interview drill block**: stops asking for more drills;
  an interview session still writes its report for the finished attempts + joined feedback (016
  abort semantics unchanged); the standalone run prints its summary for what was completed.
- **No cross-session history**: weak-sound prioritisation falls back to the curated default order.
- **`--listen-only` or `resume`**: no drills (live-only feature) — unchanged from 016.
- **A session that runs no drills/pronounce**: the report is byte-for-byte identical to a pre-feature
  report (the 016 guarantee holds — retry/weak-sound data is additive and only present when drills
  ran).

## Requirements *(mandatory)*

### Functional Requirements

**Hear → say → see → retry loop (P1)**

- **FR-001**: Before each drill, when a TTS engine and playback are available, the system MUST play
  the drill's target audio (synthesised with the existing local TTS) so the learner hears the correct
  pronunciation before being asked to read it.
- **FR-002**: When the terminal is interactive, the system MUST let the learner replay the target
  audio on demand before recording, and then record when the learner is ready.
- **FR-003**: After scoring a drill, when a sound was flagged and the per-item retry budget is not
  exhausted, the system MUST offer an immediate retry on the **same** item: re-play the target,
  re-record, and re-score it.
- **FR-004**: The retry MUST be **bounded** by a configured per-item limit (default 1, never
  unbounded), and MUST report whether the flagged sound improved, in calibrated, non-blaming language.
- **FR-005**: When no TTS/playback is available, the system MUST silently skip the hear-first and
  replay steps and still record and score the drill (graceful degradation; the 016 behaviour).
- **FR-006**: All hear-first, replay, and retry feedback MUST follow the 016 calibration: lead with
  detection ("a sound was off"); present any phone-level diagnosis as a hedged suggestion; an
  improvement on retry is stated encouragingly, never as a graded verdict.

**Sentence-level drills (P2)**

- **FR-007**: The bundled drill bank MUST include natural, useful **sentences** as base drills (each
  more than one word, several resembling technical-interview phrasing), each tied to a target
  contrast, with the target sound at an unambiguous position in the sentence.
- **FR-008**: Each bundled drill (sentence or word) MUST carry its canonical phoneme sequence in the
  model's symbol set, available offline (bundled, no runtime grapheme-to-phoneme service or network),
  exactly as in 016.
- **FR-009**: Isolated minimal-pair word drills MUST remain available as bounded follow-ons routed
  from a flagged contrast (the 016 routing is preserved).

**Standalone `pronounce` mode (P3)**

- **FR-010**: The system MUST provide a dedicated `pronounce` command that runs the hear → say → see →
  retry loop over a set of drills outside an interview session, user-paced, for as long as the learner
  wants, ending cleanly on quit.
- **FR-011**: In standalone mode the safety gate MUST consider **only live available memory** (no
  feedback engine is resident); it MUST NOT apply the interview-session rule that a configured local
  feedback engine makes drills unsafe. This MUST be a distinct, tested gate variant — the
  interview-session gate (016) is unchanged.
- **FR-012**: When live free memory is below the safe threshold, standalone mode MUST NOT load the
  model by default, MUST explain why in plain language, and MUST offer the same explicit freeze-warned
  override as 016 before proceeding.
- **FR-013**: Standalone mode MUST ensure the required local models (the pronunciation model and the
  TTS model) are present, fetching any absent model **only** through the existing resilient
  consent/download flow (size disclosure, resumable). It MUST NOT need or load the speech-recognition
  (ASR) feedback models. Declining a download exits cleanly with a hint; nothing downloads silently.
- **FR-014**: Standalone mode MUST end with a short, encouraging summary (count of drills, the
  trickiest sound) and MUST NOT write an interview session report (it is not an interview session).

**Weak-sound prioritisation (P4)**

- **FR-015**: Within a run, the system MUST bias drill selection toward contrasts the learner is
  getting wrong (the 016 follow-on routing, strengthened by an in-run tally of flagged contrasts).
- **FR-016**: The system SHOULD persist a lightweight per-contrast difficulty tally across sessions
  (in the existing derived store) so future runs order base drills toward historically weak contrasts;
  this MUST degrade gracefully to the curated default order when there is no history, and MUST be
  rebuildable/derived (never required, never schema-breaking).
- **FR-017**: When a run flagged contrasts, the system MUST surface a short "tricky sounds" summary
  (in the standalone closing summary and, for an interview session, additively inside the existing
  Pronunciation report section). A run with no flags MUST add nothing (preserving byte-identity).

**Build-time correctness safeguard (P2 dependency)**

- **FR-018**: The repository MUST include an automated **live** correctness harness that, for every
  bundled drill, renders the prompt text with the real local TTS, runs it through the real scorer, and
  asserts it scores **clean** (no false flags on the target). A drill whose canonical sequence is
  wrong fails this harness.
- **FR-019**: This harness MUST be a clearly-marked, self-skipping live test (like the existing
  `live_asr` marker) that is **excluded from the default test suite** and skips automatically when the
  model/TTS are absent — it MUST NOT load any model in the default suite.

**Offline, additivity & gate (cross-cutting)**

- **FR-020**: After the one-time model download, every path of this feature (hear-first TTS, scoring,
  canonical phonemes, weak-sound tally) MUST make zero network calls; the offline guarantee MUST be
  preserved.
- **FR-021**: The feature MUST change no grammar/coaching analysis, prompts, or outputs; the
  grammar/coaching report MUST be identical whether or not drills ran.
- **FR-022**: All new persisted data (per-item retry results, weak-sound tally, standalone results)
  MUST be additive and optional. The report `schema_version` MUST stay **1**, no existing field may be
  made required, and a session that ran no drills MUST yield a **byte-for-byte identical** report.
- **FR-023**: `speakloop --help` MUST continue to load no engine/model package; all heavy imports
  (the scorer's torch/transformers, the TTS engine) MUST stay function-local in their single wrapper
  files, and the new `pronounce` command MUST NOT break this.

**Config, bounds & docs**

- **FR-024**: New behaviour MUST be governed by optional user-configuration keys with silent defaults
  in the YAML config: a TTS-playback toggle (default on) and a per-item retry count (default 1). No
  non-YAML configuration is introduced.
- **FR-025**: The interview drill block MUST remain bounded (a small number of base drills + bounded
  follow-ons + bounded retries) so it cannot run unboundedly during the feedback wait. The standalone
  loop is user-paced and ends on the learner's command.
- **FR-026**: The README/quickstart MUST document the trainer loop (hear-first, retry, sentences), the
  `pronounce` command, and the new config keys, alongside the unchanged 016 gating.
- **FR-027**: All user-facing output for this feature MUST be in English.

### Key Entities *(include if feature involves data)*

- **Drill (sentence or word)**: A read-aloud item — target text, the contrast it exercises, its
  bundled canonical phoneme sequence, and the target index/indices carrying the contrast sound.
- **Drill bank**: The bundled, curated set of drills — now sentence-led, with word minimal-pairs as
  follow-ons, each with offline canonical phonemes; plus selection/ordering that can be biased toward
  weak contrasts.
- **Drill attempt + retry result**: One read-aloud attempt's outcome (the 016 `DrillResult`) plus, for
  a retried item, the follow-up attempt's outcome and an "improved/still-off" comparison.
- **Weak-sound tally**: A lightweight per-contrast difficulty count kept across sessions in the
  derived store, used to bias future selection; rebuildable, optional, never schema-breaking.
- **Standalone session**: A user-paced `pronounce` run that produces a terminal summary and updates
  the weak-sound tally, but no interview session report.
- **Standalone safety decision**: A SAFE/UNSAFE estimate from live memory only (no feedback engine),
  distinct from the interview-session decision.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In every drill where a TTS engine is available, the target is played before the learner
  is asked to read it — verified for both the interview drill block and the standalone mode.
- **SC-002**: A flagged item offers at most the configured number of retries (default 1) and never
  loops past it — verified deterministically with a faked scorer that always flags.
- **SC-003**: Base practice items in the bundled bank are sentences (more than one word) for the
  primary contrasts; word drills appear only as follow-ons.
- **SC-004**: The standalone `pronounce` mode runs the full loop with its gate using the live-memory
  check only (a configured local feedback engine does not block it), while an interview session in the
  same configuration still skips drills — verified by separate tests.
- **SC-005**: With a recorded weak contrast, a new run orders that contrast's drills first; with no
  history, the curated default order is used unchanged.
- **SC-006**: The build-time correctness harness scores **every** bundled drill clean (no false flags
  on the target) when run against the real model/TTS; it is excluded from the default suite and skips
  cleanly when the model/TTS are absent.
- **SC-007**: A session that runs no drills/pronounce produces a report that is byte-for-byte identical
  to the same session before this feature — verified automatically.
- **SC-008**: After the one-time download, a drills/pronounce run makes **0** network calls on the
  default path; `speakloop --help` loads **0** engine/model packages.
- **SC-009**: Standalone mode loads the pronunciation model **0%** of the time when live free memory is
  below the safe threshold under the default setting (the 016 safety promise extends to standalone).

## Assumptions

- **Reuse 016 wholesale**: the wav2vec2 CTC phoneme scorer, the pure-numpy GOP/forced-alignment, the
  bundled canonical-phoneme approach, the engine/RAM gate, the calibrated wording, and the aria2
  consent/download flow are all reused; this feature adds the loop, sentences, standalone mode, and
  weak-sound focus on top.
- **Hear-first uses the existing TTS**: the local Kokoro TTS already used for the question/ideal-answer
  and warm-up/follow-ups synthesises the target; playback uses the existing blocking playback path.
  Synthesised target clips are cached by the existing TTS clip cache; nothing new is persisted as
  audio.
- **Canonical phonemes for sentences are a flat concatenation of per-word phoneme sequences in the
  model's symbol set, with no explicit word-separator token** — the CTC forced alignment already
  inserts blanks between canonical tokens, so word boundaries need no special symbol. The target index
  points at the contrast phone within the flat sequence. This avoids any dependency on whether the
  model vocab contains a space token.
- **Sentences are authored conservatively and validated by the harness**: bundled sentences are kept
  short, are built where possible from already-validated word phoneme sequences plus simple connective
  words, and place the target contrast on an unambiguous word-initial position. The flag decision
  centres on the target index, so minor vowel-symbol drift elsewhere does not change the contrast
  check (the 016 property). The live TTS-through-scorer harness (FR-018) is the authoritative
  pre-ship validation of every canonical sequence; it must be run on a model-equipped machine before
  the bank is considered final (mirroring how 016's canonical sequences are "re-validated on a real
  run").
- **Standalone needs TTS + the pronunciation model, not ASR**: scoring uses the wav2vec2 phoneme model
  directly on the recorded audio; the interview speech-recognition models are not needed standalone, so
  the standalone mode provisions only the TTS phase + the pronunciation model.
- **Standalone writes no markdown report**: it is not an interview session; it prints a closing
  summary and updates the derived weak-sound tally only. The report schema is therefore untouched by
  standalone runs.
- **Retry compares the target sound's flag status**: an item "improved" when the previously-flagged
  target sound is no longer flagged on the retry (or its goodness score clearly improved); otherwise it
  is "still off". This is detection-level (reliable), consistent with the 016 calibration; no graded
  score is asserted.
- **Weak-sound memory lives in the existing derived store** (`~/.speakloop/store.json`), which is
  rebuildable and additive; the report frontmatter is not extended for it. The "tricky sounds" line in
  the report nests inside the existing additive pronunciation drill data, so a no-drills report stays
  byte-identical.
- **Same conservative gate threshold**: the standalone live-memory threshold reuses the existing
  `pronunciation_min_free_mb` default; borderline machines err toward skipping, with the same
  freeze-warned override.
- **Device target**: Apple Silicon, ~18 GB unified memory, consistent with the rest of the project and
  with 016.

## Out of Scope / Future

- **Prosody / stress / intonation scoring** (pitch, rhythm, "natural intonation").
- **Scoring spontaneous interview answers** (reference-free "this word may be mispronounced" flags).
- **General text-to-pronunciation for arbitrary user-supplied sentences** (drills remain a curated,
  bundled bank with bundled canonical phonemes).
- **MPS / GPU inference** for the pronunciation model (CPU only, as in 016).
- **Any change to grammar/coaching analysis, the report schema version, or offline-by-default.**
