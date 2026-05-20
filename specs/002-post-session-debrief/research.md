# Research — Post-Session Interactive Debrief (Phase 0)

This document records the **integration-layer and design decisions** for the
post-session debrief feature. Engine selections (TTS/ASR/LLM) are settled in
`doc/research_*.md` and are NOT re-litigated. The grammar catalog and impact
ranking derive from `doc/research_methodology.md` §1.1 / §1.3 (Constitution
Principle X — the methodology doc is authoritative).

Three decisions were called out explicitly by the planning directive:
(a) Persian-L1 catalog file location and format, (b) the impact-ranking
algorithm, (c) `rich.live` vs `rich.markdown` for the in-place renderer. Each is
written as Decision / Rationale / Alternatives. Supporting decisions follow.

---

## (a) Persian-L1 error catalog — location and format

**Decision**: Ship the catalog as a versioned YAML data file at
`src/speakloop/feedback/persian_l1_catalog.yaml`, loaded once by a new small
module `feedback/catalog.py` into frozen dataclasses. Each entry carries:
`id` (kebab-case), `label` (human-readable), `transfer_reason` (one-line B1–B2
explanation = the "Because:" line), `impact_rank` (1 = highest, from methodology
§1.1), `detection_hints` (short cues fed into the LLM prompt), and
`examples` (wrong → right pairs). The seed set is the patterns documented in
`doc/research_methodology.md` §1.3; the **open-bucket mechanism is preserved** —
the analyzer may still surface non-catalog patterns, which receive a default
mid-low impact weight and require `occurrence_count >= 2` (unchanged FR-002).

**Rationale**:
- YAML is the project's data idiom (Constitution Non-Negotiable: user config is
  YAML) and lets the catalog be reviewed/extended in a PR without touching
  analyzer logic — the linguistic content and the detection code evolve
  independently (Principle IV, single responsibility).
- A data file makes the methodology→catalog traceability auditable: each entry
  cites the methodology pattern number it came from, satisfying Principle X.
- Loading into frozen dataclasses at import time (one parse, cached) keeps the
  hot path dependency-free and deterministic; a malformed catalog fails loudly
  at load, not mid-session.
- The current `SEED_PATTERNS` tuple in `grammar_analyzer.py` is a hardcoded
  string list with no transfer reason, impact, or correction structure — it
  cannot carry the new fields. The catalog file is its structured successor.

**Alternatives considered**:
- *Python constant module (`feedback/catalog.py` with a literal list)* — simplest,
  no IO/parse path, but mixes linguistic data into code and is harder to review
  as data. Rejected as primary, but the loader still exposes the catalog as
  Python objects so consumers never parse YAML themselves.
- *Put it in `content/`* — `content/` owns user Q&A; the catalog is system
  reference data, not user content. Wrong module (Principle IV).
- *User-overridable catalog under `~/.speakloop/`* — out of scope (v2 "persistent
  user preferences"); v1 ships one in-repo catalog.

---

## (b) Impact-ranking algorithm

**Decision**: Rank patterns **deterministically** at report-build time, not by
asking the LLM for a score. The sort key is a tuple, ascending:
`(catalog_impact_rank, -occurrence_count, first_attempt_ordinal)`.
- Catalog patterns inherit `impact_rank` from `persian_l1_catalog.yaml` (derived
  from methodology §1.1: practice–target mismatch / proceduralization of
  inflection / 3sg-s & aux-be / L1 transfer for prepositions·articles·possessor /
  fatigue — mapped to the concrete error categories in §1.3).
- Open-bucket (non-catalog) patterns get a fixed default rank that places them
  **below** all catalog patterns, tie-broken by `occurrence_count` then earliest
  appearance.
- The resolved `impact_rank` is **persisted** on each pattern in the report
  frontmatter (additive field) so the renderer and the read-aloud order are
  reproducible from the file alone and stable across runs.

**Rationale**:
- The whole feature exists because LLM output is unreliable; making the *ranking*
  LLM-decided would reintroduce non-determinism into the one thing the UX leans
  on most ("the single most important thing to fix"). A static, methodology-
  grounded weight is reproducible, testable against a gold set (SC-002), and
  explainable.
- "Impact on interview comprehensibility" (FR-005) is exactly what methodology
  §1.1 ranks; reusing that ranking keeps the product decision traceable to the
  research rather than to a model's guess.
- Persisting the rank means the renderer is a pure function of the report file —
  no recomputation, no drift between the written `.md` and the on-screen debrief.

**Alternatives considered**:
- *LLM-assigned impact score* — rejected (non-deterministic; defeats the purpose).
- *Rank by raw occurrence_count* — explicitly rejected by FR-005 (frequency ≠
  impact; a single comparative-form error can hurt comprehensibility more than
  five dropped articles).
- *Hybrid where the LLM proposes and we clamp to catalog* — more moving parts for
  no reproducibility gain; the catalog already encodes impact.

---

## (c) In-place renderer — `rich.live` vs `rich.markdown`

**Decision**: Render the debrief from an in-memory **view model** built from the
`Session` object using **custom `rich` renderables** (`Panel`, `Table`, `Group`,
`Text`), driven by **`rich.live.Live`** so the currently-read section can be
highlighted as audio progresses. Do **not** render the report by feeding the
saved Markdown file to `rich.markdown.Markdown`. `rich.markdown` may still be
used for any free-text prose block inside a card, but it is not the layout engine.

**Rationale**:
- The UX requirements need fine layout control that `rich.markdown` cannot give:
  a bordered **Top-priority banner** (FR-011), three-line **pattern cards** with
  visually distinct lines (FR-012), **green/yellow/red trend coloring** on the
  attempt table (FR-013), **collapsed transcripts** with a "+143 words" indicator
  (FR-014), a **section highlight** that moves with the audio (FR-019), and a
  **"3 of N sections"** progress line. These are composed renderables, not
  markdown.
- `rich.live.Live` lets the same composed view be re-rendered in place as the
  highlighted section advances, then handed off to the menu — no scrolling wall
  of text, supporting the 90-second pacing target (SC-005) and the "feels like a
  tutor" bar.
- Building from the `Session`/view model (not by re-parsing the `.md`) means the
  report file stays the persistence artifact while the screen is driven by typed
  data — cleaner, and avoids a Markdown round-trip that could desync from the
  written file.
- `rich` is already a Constitution Non-Negotiable dependency; `Live`, `Panel`,
  `Table`, `Group`, `Text` are all first-party. **Zero new third-party deps.**

**Alternatives considered**:
- *`rich.markdown.Markdown(open(report).read())`* — fastest to write, but cannot
  produce the banner/cards/section-highlight/trend-color UX and would require
  re-parsing the file. Rejected as the layout engine.
- *Plain `console.print` without `Live`* — works for a static dump but cannot
  move the highlight in sync with audio (FR-019). Used only as the graceful
  fallback when the terminal reports no control capability (see degradation).
- *A TUI framework (Textual, urwid)* — overkill, adds a heavy dependency, and the
  Constitution forbids non-`rich` UI surfaces in v1. Rejected.

---

## (d) Replay loop and engine residency (no model reload)

**Decision**: Move the per-question loop **up into the CLI practice flow**
(`cli/practice.py`, optionally extracted to `sessions/practice_loop.py`). Engines
(`KokoroEngine`, `ParakeetEngine`, and the `QwenEngine` held by the grammar
analyzer closure) are constructed **once before the loop** and **injected** into
every `run_session(...)` call. Replay (`r`) re-enters the loop body for the same
question; the engine instances are reused, so no model reloads.

**Rationale / required change**:
- `run_session` currently lazily constructs `ParakeetEngine()` *inside* the
  function when `asr_engine is None` (coordinator.py:241-244). On a naive replay
  this would re-instantiate ASR each cycle. The fix is to hoist ASR construction
  into the practice loop and pass the instance in — the coordinator already
  accepts an injected `asr_engine`, so this is a call-site change, not an
  interface change. This is the load-bearing requirement behind SC-004
  ("replay … under 3 seconds, no model reload").
- The `QwenEngine` is already shared across calls via the `_build_grammar_analyzer`
  closure (practice.py:296-311) — its `_load()` is lazy and memoized, so reuse is
  free once warm. Kokoro is already injected. So only ASR needs hoisting.
- Replay skips `installer.ensure_models`, `doctor` pre-check, and progress UI
  (those run once at launch) — satisfying FR-026.

**Alternatives considered**:
- *Loop inside `run_session`* — would entangle session orchestration with menu
  control flow and question selection; violates single responsibility. The loop
  belongs at the CLI/orchestration layer.
- *Re-read the report Markdown to feed the debrief* — rejected; `run_session`
  will return the `Session` object so the debrief renders from memory (see
  data-model.md). The file is still written for persistence/trends.

---

## (e) ASR-garble (incoherence) evidence filter — offline, dependency-free

**Decision**: Add a deterministic coherence filter (FR-006) that runs **after**
the existing verbatim-substring check. A quote is dropped when it fails a cheap
structural test: too few alphabetic tokens, or the fraction of tokens not present
in a shipped compact high-frequency English wordlist
(`src/speakloop/feedback/common_words.txt`, ~3–5k words) exceeds a threshold,
after excluding the user's known technical vocabulary tokens already attested
across the transcripts. A pattern left with no coherent evidence is dropped
entirely.

**Rationale**:
- Must be offline (Principle II) and add no heavy NLP dependency
  ("standard library over dependencies"). A small shipped wordlist + token-ratio
  heuristic catches the documented failure ("Killing RT check") without a parser.
- Running it as a post-filter keeps the existing verbatim guarantee (FR-007)
  intact and isolates the new rule for unit testing against the gold set.
- Excluding attested technical terms avoids false-dropping legitimate jargon
  ("Kotlin", "coroutine", "dispatcher") that won't be in a general wordlist.

**Alternatives considered**:
- *Rely on the LLM to self-censor garble in the prompt* — unreliable on its own;
  the deterministic post-filter is the guarantee. The prompt still instructs the
  model to avoid citing garble (defense in depth).
- *`/usr/share/dict/words` (system dictionary)* — present on macOS but not
  guaranteed/portable and unversioned; a shipped wordlist is reproducible and
  testable. Rejected.
- *Heavyweight language-detect / spellcheck libs* — dependency weight unjustified
  for a token-ratio check. Rejected.

---

## (f) Interactive menu and keypress handling

**Decision**: Implement the debrief menu (`r`/`n`/`q` + `replay`/`new`/`quit`,
default `replay`, arrow-key navigation, Enter = default) and the any-key
skip-during-audio in a new `debrief/menu.py`, reusing the project's existing
two-tier tty pattern (`termios` + `tty.setcbreak`, with a `/dev/tty` fallback and
a line-buffered fallback for piped input) already proven in `cli/practice.py`.
Arrow keys are read as escape sequences (`\x1b[A` / `\x1b[B`).

The menu also accepts a **transcript-toggle key `t`** (FR-014/FR-024, per the
2026-05-20 clarification). Unlike `r`/`n`/`q`, `t` is **not** a terminal
`DebriefChoice` — it toggles full-transcript expansion in place (re-rendering the
`Live` view) and keeps the menu open, looping until the user picks replay/new/quit.
This keeps expansion an in-debrief interaction rather than a control-flow exit.

**Rationale**:
- Reuses a pattern already debugged for macOS/`uv run` quirks (practice.py
  `_read_key`/`_cbreak_read`), rather than adding an interactive-prompt
  dependency ("boring over novel"). The line-buffered fallback keeps it testable
  without a real tty (Development Guidelines).
- Keeping menu input inside `debrief/` respects module boundaries; the shared
  keypress logic may later be factored into a small `sessions/keys.py` helper
  consumed by both the listen loop and the debrief — noted as an optional
  refactor, not required for this feature.

**Alternatives considered**:
- *`typer`/`click` prompts or `questionary`/`prompt_toolkit`* — new dependency and
  heavier than needed; the existing pattern already covers single-key + word
  input. Rejected.

---

## (g) Cross-attempt narrative and "Top priority" — deterministic

**Decision**: Generate the narrative and the single "Top priority" line
**deterministically** in a new `feedback/narrative.py`, not via the LLM. The
narrative extends the existing `_cross_attempt_paragraph` logic (what improved /
what stayed the same across the 4/3/2 rounds). The Top priority is selected by a
**most-impactful-wins** rule (FR-008, per the 2026-05-20 clarification): score
both candidate sources on a common impact scale — each grammar pattern by its
`impact_rank`, and each fluency dimension (e.g. filler density, speech-rate
collapse) by a deterministic severity heuristic — then surface the single
highest-impact item. A fluency issue MAY therefore become the Top priority even
when grammar patterns also exist, if it outranks them; conversely a severe
grammar pattern still wins over mild disfluency. With no grammar patterns and no
notable fluency problem, the Top priority degrades to a sensible default message.
Both narrative and Top priority are **persisted** in the frontmatter (additive
fields) so the renderer and read-aloud are reproducible.

The fluency severity heuristic and the cross-scale comparison live in
`feedback/narrative.py` with fixed thresholds (documented inline and unit-tested),
keeping selection deterministic and explainable — no LLM, no second round-trip.

**Rationale**:
- Determinism and testability (SC-001/SC-002) — the "single most important thing"
  must be stable and explainable, and it is already implied by the persisted
  impact ranking (decision b). No second LLM round-trip, helping the 90-second
  budget (SC-005).
- The existing cross-attempt prose is already deterministic; this extends a
  proven approach rather than introducing model variance.

**Alternatives considered**:
- *LLM-written narrative/priority* — reintroduces variance and latency for the
  most prominent UX element. Rejected. (The LLM's job stays narrowly scoped to
  detecting grammar patterns + producing the corrected version and, for
  open-bucket items, a transfer reason.)

---

## (h) Pacing / performance budget

**Decision**: Target ≤ 90 s for a typical 3-pattern debrief (SC-005) by:
synthesizing each educational section's audio through the **existing TTS engine
with its content-addressed cache** (`tts/cache.py`), so repeated corrected
phrases and replays hit cache; rendering the visual debrief immediately (no wait
on audio); and allowing any-key skip at any point (FR-020). Replay returns to
"press space to begin attempt 1" in < 3 s by reusing resident engines (decision
d). TTS/playback failures are caught and the menu appears immediately (FR-029).

**Rationale**: The long pole is audio synthesis+playback; caching and skip-anytime
keep the worst case bounded and the user in control. No new perf-sensitive code
paths beyond TTS calls already characterized in Phase A.

**Alternatives considered**:
- *Pre-synthesize all sections before showing anything* — delays first paint and
  hurts perceived pacing. Rejected; render first, stream audio.

---

## Summary of new/changed dependencies

**No new third-party dependencies.** All rendering uses `rich` (already
mandated); audio uses the existing TTS engine + `audio.playback`; the coherence
wordlist and the catalog ship as in-repo data files. This keeps the
Constitution's "standard library over dependencies" and offline guarantees intact.
