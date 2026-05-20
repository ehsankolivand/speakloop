# Implementation Plan: Post-Session Interactive Debrief

**Branch**: `002-post-session-debrief` | **Date**: 2026-05-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-post-session-debrief/spec.md`

## Summary

Two coupled improvements to the Phase-C feedback experience, built on the existing
v1 architecture without breaking the `schema_version: 1` report format:

1. **Trustworthy feedback content** — redesign the LLM grammar analyzer around a
   versioned Persian-L1 error catalog (accurate labels, one-line transfer-reason
   explanations, verbatim "You said / Better / Because" corrections), drop
   ASR-garble evidence deterministically, rank patterns by methodology-grounded
   impact (not frequency), and add a deterministic cross-attempt narrative with a
   single persisted "Top priority" chosen by a most-impactful-wins rule across
   grammar and fluency.
2. **Closed practice loop in the terminal** — a new `debrief/` module renders the
   report in place with `rich` (top-priority banner, three-line pattern cards,
   trend-coloured attempt table, collapsed transcripts), reads only the
   educational parts aloud via the existing TTS engine with a moving section
   highlight and "X of N" progress, then shows an `r`/`n`/`q` menu (plus a `t`
   transcript-toggle). Replay reuses resident engines (no model reload) and
   returns to the listen phase in < 3 s.

The three design decisions called out by the directive — catalog
location/format, impact-ranking algorithm, and `rich.live` vs `rich.markdown` —
are resolved in [research.md](./research.md) §(a), §(b), §(c). Engine choices are
unchanged and continue to cite `doc/research_*.md`; the catalog and ranking trace
to `doc/research_methodology.md` §1.1 / §1.3 (Constitution Principle X).

## Technical Context

**Language/Version**: Python 3.12 (unchanged; per v1 plan and Constitution).

**Package manager**: `uv` (Constitution-mandated). Entry point unchanged:
`uv run speakloop`.

**Primary Dependencies**: No new third-party dependencies. Rendering uses `rich`
(`Live`, `Panel`, `Table`, `Group`, `Text` — already mandated); audio uses the
existing `tts` engine + `audio.playback`; LLM stays `mlx_lm` via `QwenEngine`.
New in-repo **data files** only: `feedback/persian_l1_catalog.yaml` and
`feedback/common_words.txt` (coherence wordlist).

**Storage**: Filesystem only (unchanged). Reports remain Markdown + YAML
frontmatter under `data/sessions/`; frontmatter stays `schema_version: 1` with
**additive** fields (Principle IX; Development Guidelines "Stable report schema").

**Testing**: `pytest`. New unit tests for catalog loading, ranking, the coherence
filter, narrative/top-priority selection, the debrief view model, and renderer
output (capture `rich` console). A small **human-labelled gold set** of
transcript→expected-pattern fixtures under `tests/fixtures/` backs SC-002/SC-003.
Live model calls remain forbidden; the LLM is stubbed in tests.

**Target Platform**: macOS arm64 (Apple Silicon, M3 Pro 18 GB) — unchanged.

**Project Type**: Single-project Python CLI under `src/speakloop/` — unchanged.

**Performance Goals**:
- Full debrief (audio + visual + menu) ≤ 90 s for a typical 3-pattern report
  (SC-005); visual paints before audio; any-key skip at any time.
- Replay returns to "press space to begin attempt 1" in < 3 s with **no model
  reload** (SC-004) — requires hoisting ASR engine construction out of
  `run_session` into the practice loop (research.md §d).
- Grammar analysis stays within the existing Phase-C report budget; no second LLM
  round-trip (narrative/top-priority are deterministic).

**Constraints**:
- Offline-only after install (Principle II); coherence wordlist + catalog ship
  in-repo, no network.
- All user-facing strings English (Principle I).
- `schema_version: 1` preserved; only additive frontmatter changes; trends reader
  keeps working unchanged (FR-031).
- Ctrl+C during the debrief must not corrupt the already-written report or leave
  temp audio (extends FR-016 invariant).
- Graceful degradation: no LLM model → Phase-B debrief with a one-line grammar
  placeholder; TTS failure → visual debrief + menu, no hang (FR-028, FR-029).

**Scale/Scope**: Single user, single machine. One new module (`debrief/`), three
extended modules (`feedback/`, `sessions/`, `cli/`), two new in-repo data files.

## Constitution Check

*Gate status before Phase 0 research and re-checked after Phase 1 design:*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. English-Only UI | PASS | All new strings (debrief, menu, narrative, catalog labels/reasons) are English. |
| II. Offline-First | PASS | No network. Catalog and coherence wordlist are in-repo data; TTS/ASR/LLM already local. |
| III. Privacy by Design | PASS | No new data leaves the device; reports stay under `data/sessions/`. |
| IV. Modular by Design (NON-NEGOTIABLE) | PASS by design | New `debrief/` module is single-responsibility (post-session render+audio+menu) and ships its own `CLAUDE.md`. Content-quality changes stay within `feedback/`. |
| V. Swappable Engines | PASS | No engine-specific imports added outside engine wrapper files. `debrief/` consumes TTS only through the injected `TTSEngine` Protocol; the analyzer consumes LLM only through `LLMEngine`. |
| VI. Resumable Model Downloads | PASS | Installer untouched. |
| VII. Apple Silicon Primary Target | PASS | Targets M3 Pro 18 GB; reuses resident MLX engines. |
| VIII. Easy Install for Everyone | PASS | `--help` still model-free; new `--no-audio` flag adds no model requirement. |
| IX. Obsidian-Compatible Reports | PASS | Frontmatter stays `schema_version: 1`; new fields are additive and render cleanly; filename convention unchanged. |
| X. Research is Part of the Repo | PASS | Catalog/ranking cite `doc/research_methodology.md` §1.1/§1.3; this `research.md` records the integration-layer decisions (catalog format, ranking algo, renderer lib). |
| XI. AI-Collaborator Friendly | PASS | New module is independently loadable with its own `CLAUDE.md`; changes to existing modules are local and documented. |
| XII. Iterative Delivery | PASS | Feature degrades to Phase-B content when the LLM is absent; the three user stories ship incrementally (US1 content → US2 visual+menu+replay → US3 audio sync → US4 degradation/onboarding). |

**Non-Negotiable Constraints**: Python 3.12 ✓ · `uv` ✓ · model storage unchanged
✓ · YAML for the catalog data file ✓ · CLI with `rich` only (no GUI/TUI
framework) ✓ · no external services ✓ · MIT ✓ · public repo ✓.

**Gate verdict**: PASS. No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-post-session-debrief/
├── plan.md              # this file
├── research.md          # Phase 0 — (a) catalog, (b) ranking, (c) renderer + supporting decisions
├── data-model.md        # Phase 1 — additive frontmatter fields + view-model entities
├── quickstart.md        # Phase 1 — exercise the debrief end-to-end locally
├── contracts/           # Phase 1
│   ├── debrief-interface.py        # Python Protocols the debrief module exposes
│   ├── persian-l1-catalog.yaml     # catalog data-file schema (+ seed entries shape)
│   └── report-frontmatter-v1-additive.yaml  # additive frontmatter fields (schema_version stays 1)
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # NOT created by /speckit-plan; produced by /speckit-tasks
```

### Source Code (repository root)

Changes are localized to one new module and three existing modules; the
twelve-module v1 map is otherwise unchanged. New/changed paths only:

```text
src/speakloop/
├── feedback/                         # CONTENT QUALITY (extended)
│   ├── grammar_analyzer.py           # CHANGED: catalog-aware prompt; emits corrected version + transfer reason; runs coherence filter; assigns persisted impact_rank
│   ├── catalog.py                    # NEW: loads persian_l1_catalog.yaml into frozen dataclasses; open-bucket default weight
│   ├── persian_l1_catalog.yaml       # NEW: seed catalog (id, label, transfer_reason, impact_rank, detection_hints, examples) — cites methodology §1.3
│   ├── common_words.txt              # NEW: compact high-frequency English wordlist for the coherence filter (FR-006)
│   ├── coherence.py                  # NEW: deterministic ASR-garble evidence filter (FR-006), excludes attested technical tokens
│   ├── narrative.py                  # NEW: deterministic cross-attempt narrative + single Top-priority (FR-008)
│   ├── frontmatter.py                # CHANGED: additive fields on GrammarPattern (explanation, impact_rank, per-evidence corrected) + Session (cross_attempt_narrative, top_priority); schema_version stays 1
│   ├── report_builder.py             # CHANGED: render new fields into the Markdown body (Top-priority section, three-line fixes); Phase-B placeholder preserved
│   ├── markdown_writer.py            # unchanged
│   └── CLAUDE.md                     # CHANGED: document new public surface
├── debrief/                          # NEW MODULE — post-session interactive debrief
│   ├── __init__.py                   # public surface re-exports
│   ├── view_model.py                 # builds DebriefViewModel from a Session (sections, audio-eligibility, trend deltas, collapsed transcript previews, first-time flag)
│   ├── renderer.py                   # rich.Live + Panel/Table/Group/Text: banner, pattern cards, trend colours, collapsed transcripts, section highlight, "X of N" progress
│   ├── audio_player.py               # synth educational sections via injected TTSEngine + play_fn; progress; any-key skip; graceful TTS failure
│   ├── menu.py                       # r/n/q + replay/new/quit (default replay, arrow-key nav) + `t` transcript-toggle (in-place, non-terminal); two-tier tty reader (reused pattern)
│   ├── debrief.py                    # orchestrates announcement → audio+highlight → menu; returns the user's choice
│   └── CLAUDE.md                     # NEW: module contract (Principle IV)
├── sessions/
│   └── coordinator.py                # CHANGED: run_session returns the Session object alongside the report path (additive result); accepts injected asr_engine (already does) — caller now always injects it
├── cli/
│   ├── practice.py                   # CHANGED: construct engines once; loop listen → session → debrief → menu; handle replay/new/quit with no reload; add --no-audio flag; first-time detection
│   └── CLAUDE.md                     # CHANGED: note --no-audio and the replay loop
└── (all other modules unchanged)

tests/
├── fixtures/
│   ├── transcripts/                  # NEW: gold-set transcripts with expected patterns (incl. the documented failures: "I like to programming", "eight year experience", "even bigger than", "Killing RT check")
│   └── reports/                      # NEW: sample Session/report fixtures for renderer + view-model tests
├── unit/
│   ├── feedback/                     # NEW/EXTENDED: catalog loader, coherence filter, ranking, narrative/top-priority, frontmatter additive round-trip
│   └── debrief/                      # NEW: view_model, renderer (capture rich output), menu parsing, audio_player skip + TTS-failure paths
└── integration/
    └── phase_c_debrief_test.py       # NEW: full session → report → debrief render → menu choice → replay with stubbed engines (no reload)
```

**Structure Decision**: Add exactly one new first-level module, `debrief/`, with
its own `CLAUDE.md` (Principles IV, XI). Content-quality work is contained within
`feedback/` (the module that already owns report assembly and the grammar
analyzer). The renderer/audio/menu concern is genuinely separate from report
*assembly*, so it earns its own module rather than bloating `feedback/` or
`cli/`. Engine access stays behind the existing `TTSEngine`/`LLMEngine` Protocols
— no engine-specific import crosses a new boundary (Principle V).

### Phase shipping order within this feature (Iterative Delivery — Principle XII)

| Slice | Ships | User-visible outcome |
|-------|-------|----------------------|
| **US1** | `feedback/catalog.py`, `persian_l1_catalog.yaml`, `coherence.py`, `common_words.txt`, `narrative.py`, analyzer + frontmatter + report_builder changes, gold-set fixtures | The written report is accurate and actionable (correct labels, verbatim "You said/Better/Because", garble dropped, impact-ranked, Top priority). Valuable even before any UI change. |
| **US2** | `debrief/` (view_model, renderer, menu, debrief), `cli/practice.py` loop + replay, `coordinator.py` result change | Report renders in-terminal with banner/cards/trend colours/collapsed transcripts; `r`/`n`/`q` menu; replay in < 3 s with no reload. Works on Phase-B content too. |
| **US3** | `debrief/audio_player.py`, audio-sync wiring in `debrief.py`, `--no-audio` flag | Educational parts read aloud with moving highlight and "X of N" progress; any-key skip; `--no-audio` path. |
| **US4** | degradation + onboarding branches across `debrief.py`/`cli` | No-LLM placeholder line; TTS-failure continues to menu; first-time orientation line. |

Each slice leaves a complete working system; later slices add capability without
breaking earlier ones.

## Complexity Tracking

No constitution violations. This section is intentionally empty.
