# Research & Decisions: Pronunciation Trainer (017)

Builds directly on 016 (`specs/016-pronunciation-drills/research.md` + `doc/research_pronunciation.md`).
All external identifiers reused here (the wav2vec2 model, Kokoro TTS, the aria2 downloader, psutil)
were already verified in 016; this file records the *new* engineering decisions for the trainer loop.
No new third-party dependency is introduced.

## D1 — Hear-first uses the existing Kokoro TTS + existing playback (no new engine)

**Decision**: Before each drill, synthesize the drill's target text with the **existing** Kokoro TTS
(`tts.KokoroEngine.synthesize(text) -> Path`) and play it with the **existing** blocking playback
(`audio.playback.play(wav)`), both already injected into the coordinator as `tts_engine` / `play_fn`.
Replay-on-demand polls the existing `key_reader` for `r`.

**Rationale**: The question/ideal-answer, warm-up, and follow-ups already speak through this exact path
(`coordinator.run_session` receives `tts_engine` + `play_fn`). Reusing it means zero new engine, zero
new model, offline-preserved, and the TTS clip cache makes a replayed/repeated target instant
(`tts/cache.py`). The interview drill block already runs concurrently with a background `_analyze`;
TTS synth + playback happen on the **main thread** only (the background thread does LLM work, never
audio), so there is no audio-device or engine contention.

**Degradation**: when `tts_engine`/`play_fn` are `None` (every existing 016 test, `--no-audio`-style
contexts) the hear-first + replay steps are skipped and the drill records+scores exactly as in 016.
The replay wait-for-key only engages when `key_reader.raw_capable` is True; otherwise the target plays
once and recording proceeds on the time budget (matches the 012 keyboard degradation model).

**Alternatives rejected**: a second/standalone TTS path (violates Principle V single-wrapper rule);
interruptible playback for the target (unnecessary — the target is short; blocking `play` is simpler
and the user controls pace via `r` before recording).

## D2 — Bounded **automatic** retry (not a yes/no prompt)

**Decision**: After a drill scores with a flagged target sound, when the terminal is interactive
(`key_reader.raw_capable`) and the per-item retry budget (`pronunciation_retries`, default **1**) is
not spent, the loop automatically does another pass on the **same** item: re-play the target → record →
re-score. It stops early once the previously-flagged target clears, and after the budget is spent it
moves on. "Improved" = the previously-flagged target index is no longer flagged on the retry (a
detection-level comparison — reliable, consistent with 016 calibration); otherwise "still a little
off". Never blaming; never unbounded.

**Rationale**: A calm automatic "let's try that once more" is a better trainer than a yes/no prompt
(less friction, fixes the sound while fresh), and it is fully deterministic to test (inject a faked
scorer + `record_fn`). Gating retry on interactivity means non-interactive contexts (the default test
suite, piped runs) behave exactly like 016 — so the 016 byte-identical and concurrency tests stay
green without modification. The retry budget is a clamped `loop.yaml` int (0 → 016 one-shot behaviour).

**Alternatives rejected**: a yes/no retry prompt (more friction, an extra key surface); unbounded
"keep trying until clear" (could loop forever on a hard sound — violates FR-004/FR-025).

## D3 — Sentence canonical phonemes = flat per-word concatenation, no word-separator token

**Decision**: Each bundled **sentence** drill's `canonical` is the **flat concatenation** of its words'
phoneme sequences in the model's symbol set, with **no** explicit space/word-boundary token. The
`targets` indices point at the contrast phone within that flat list (same shape as 016 word drills).

**Rationale**: The CTC forced alignment (`gop.forced_align`) already inserts CTC blanks **between every
canonical token** (the blank-extended sequence), so word boundaries are represented by the blank states
with no special symbol — and the runtime already drops any canonical symbol absent from the model vocab
(`wav2vec2_engine._score_against_canonical`). Depending on whether `vocab.json` contains a literal space
token would be fragile; a flat concatenation is robust either way. The 016 flag decision centres on the
`targets` index where the symbol is unambiguous, so minor vowel-symbol drift elsewhere in a sentence
does not change the contrast check (the 016 property is preserved at sentence scale).

**Authoring**: sentences are kept short, are composed where possible from already-validated 016 word
phoneme sequences plus simple connective words, and place the contrast on an unambiguous word-initial
consonant (e.g. `v`, `w`, `θ`, `ð`, `l`). `g2p_en` remains a dev-time-only authoring aid (NOT shipped,
NOT declared — it fetches NLTK over the network, the 016 offline trap). The authoritative pre-ship
validation is D4.

## D4 — Build-time correctness harness (TTS → scorer round-trip), as a live self-skipping test

**Decision**: Ship `tests/live_pron_test.py` (marker `live_pron`, excluded from the default suite,
mirrors `live_asr`/`live_llm`/`live_download`). For **every** bundled drill it renders the prompt with
the real Kokoro TTS, scores the rendering with the real wav2vec2 scorer, and asserts the result is
`scored` with **no flag at the target index** (a clean rendering of the correct words must not be
flagged). A drill whose `canonical` is wrong (mis-aligned target) fails here and must be fixed before
shipping.

**Rationale**: The hand-authored canonical sequences are the known correctness-risk surface (016). A
clean TTS rendering is a strong oracle: if the *correct* pronunciation flags the target, the canonical
sequence (or target index) is wrong. The harness reuses the exact new hear-first TTS path + the 016
scorer, so it also smoke-tests the wiring. It is a **live** test (needs the 1.3 GB model + Kokoro), so
it self-skips when either is absent (`pytest.importorskip` + a model-presence check) and never runs in
the default suite — no model is loaded by `uv run pytest`.

**Pinned constant**: register `live_pron` in `pyproject.toml [tool.pytest.ini_options] markers`
alongside `live_asr`/`live_llm`/`live_download`.

## D5 — Standalone gate variant: live-RAM only (`assess_standalone_safety`)

**Decision**: Add `gate.assess_standalone_safety(*, min_free_mb, available_mb=None) -> SafetyDecision`.
It reads live available RAM (`psutil`, function-local, the 016 `_measure_available_mb`) and returns
SAFE when `available ≥ min_free_mb` (or when RAM is unreadable → safe-cautious), UNSAFE (low memory)
below — with **no engine penalty**. The 016 `assess_safety(engine, …)` (where `engine == "local"` is
always unsafe) is **unchanged** and still governs the interview drill block.

**Rationale**: Standalone has no resident feedback model, so the interview rule "local engine ⇒ unsafe"
does not apply — that rule exists only because the local Qwen feedback model is resident in a session.
A distinct function keeps the interview safety promise intact (no weakening) while making standalone
available in the common case (FR-011). The same conservative `pronunciation_min_free_mb` default (4500)
and the same freeze-warned override are reused. `SafetyDecision.engine` is set to `"standalone"` for
clarity; the reason strings drop the "switch to a cloud engine" hint (there is no engine) in favour of
"close some apps and retry".

## D6 — Pure, UI-agnostic per-drill loop (`pronunciation/drill_runner.py`)

**Decision**: Factor the hear→say→see→retry mechanics for ONE drill into a pure function
`run_drill_item(drill, *, contrast, scorer, speak, record, key_reader, console, retries, tts_on,
scratch_dir) -> dict`. It receives injected callables — `speak(text)` (synthesize+play, or no-op),
`record(wav_path, *, label)` (records with whatever UI the caller provides) — plus the duck-typed
`scorer` and `key_reader`. It owns the sequence, the replay-on-demand loop, the bounded-retry +
improvement logic, the calibrated live prints (via `pronunciation.feedback`), and the returned item
dict. It imports **no** engine package and **no** `sessions`/`tts`/`audio` module.

`select_drills(bank, *, weak_contrasts, max_base) -> list[Drill]` (also here) orders base drills with
historically-weak contrasts first, preserving curated order within ties, falling back to curated order
when `weak_contrasts` is empty.

**Rationale**: Both callers (the interview block in `sessions/coordinator.py` with the countdown/REC UI
+ concurrent feedback, and `cli/pronounce.py`) need identical loop logic but different recording UI and
lifecycle. Injecting `speak`/`record` keeps the loop pure and unit-testable (no model/mic/tty) and
avoids a `pronunciation → sessions/tts/audio` import cycle (sessions already depends on pronunciation).
This satisfies the guardrail "pronunciation/ owns the loop logic" while the recording UI stays in
sessions and TTS stays in tts/.

## D7 — Cross-session weak-sound tally in the derived store (rebuildable)

**Decision**: Add an optional `pronunciation_contrasts` section to `store.Store`:
`contrast_id -> list[[iso_date, flagged_count]]` (chronological, mirrors the existing `patterns`
series). It is written after every **interview session that ran drills** (main thread, after the
analysis join — alongside the existing `patterns` write) and after every **standalone run** that scored
drills. `store.rebuild` folds it from each report's `pronunciation_drills.summary.contrasts_practiced`
+ per-item flags, so the interview-session contribution is **rebuildable** from `data/sessions/*.md`.
`STORE_VERSION` stays **1** (an additive section with a default is non-breaking; old stores load with
an empty tally; old code ignores the unknown key).

**Rebuild caveat (documented, matches precedent)**: standalone runs write no markdown report, so their
contribution is live-only — a manual `speakloop rebuild` drops standalone-only history, recovered as
the user practises. This mirrors the existing accepted precedent that `rebuild` does not restore the
real SRS `next_due` (store CLAUDE.md). The store remains a recoverable cache; nothing breaks.

**Use**: `cli/pronounce` and (optionally) the interview block read the tally → `select_drills` bias.
With no tally → curated order (FR-016 graceful fallback). A short "tricky sounds" line is rendered in
the standalone summary and additively inside the interview report's Pronunciation section.

**Alternatives rejected**: a new frontmatter key for the tally (would touch the report schema surface —
unnecessary; the store is the right home for derived cross-session aggregates); bumping `STORE_VERSION`
(not needed for an additive, default-empty section).

## D8 — Config keys (additive optional, YAML-only)

| Key | Default | Validation |
|---|---|---|
| `pronunciation_tts_playback` | `true` | must be `bool`, else default |
| `pronunciation_retries` | `1` | `int` clamped to `[0, 3]`, else default |

Both are read-only-with-default in `loop.yaml` (like `analysis_concurrency`); no writer is added.
`doctor` displays them. They join the 016 keys `pronunciation_drills` (auto/on/off) and
`pronunciation_min_free_mb` (reused as the standalone threshold).

## D9 — `speakloop pronounce` command shape

**Decision**: A new thin `cli/pronounce.py` + `@app.command("pronounce")` in `main.py` (the command
body defers all imports, like `practice_cmd`, so `--help` loads nothing). Flow: load config → RAM-only
gate (`assess_standalone_safety`, with the freeze-warned override on UNSAFE) → provision (`ensure_models
("A")` for Kokoro + `ensure_pronunciation_model`; decline → clean exit) → build scorer/bank/tts/play/
record/key_reader → load store tally → user-paced loop via `run_drill_item` (prioritised by
`select_drills`, `q` to quit, continue until the learner stops) → closing summary + store tally update.
It needs **no ASR** model (scoring is wav2vec2-direct), so it provisions only TTS + the pronunciation
model. Flags: `--limit N` (max base drills this run, optional) and `--drills/--no-drills`-style is not
needed (the command IS the drills). All user-facing strings English.

**Rationale**: Mirrors `practice`/`setup` wiring conventions exactly (engine-import-deferral, consent
flow, injected fakes for tests). No new module dir; documented in `cli/CLAUDE.md`.

## Open items resolved (no NEEDS CLARIFICATION remain)

- Retry: bounded automatic (default 1, clamp 0–3), interactive-only, detection-level improvement.
- Sentence canonical: flat per-word concatenation, no separator token; validated by the live harness.
- Standalone gate: RAM-only variant; 016 interview rule unchanged.
- Standalone artifact: terminal summary + store tally; **no** markdown report.
- Weak-sound memory: store section, rebuildable from reports; standalone-only history lost on rebuild
  (documented, matches SRS `next_due` precedent).
- Loop logic home: pure `pronunciation/drill_runner.py` with injected speak/record/scorer.
