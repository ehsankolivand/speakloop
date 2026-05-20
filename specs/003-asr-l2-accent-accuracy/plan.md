# Implementation Plan: ASR Accuracy on Persian-L1 Accented Technical English

**Branch**: `003-asr-l2-accent-accuracy` | **Date**: 2026-05-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-asr-l2-accent-accuracy/spec.md`

## Summary

Make the transcript layer trustworthy on Persian-L1 accented technical English so
the grammar analyzer stops flagging ASR-garble as grammar errors. Three coupled
changes inside the existing `asr/` module boundary, all built on
`doc/research_asr_l2_accent.md` (the compass for this feature, Constitution
Principle X):

1. **Default engine swap** — add `WhisperMLXEngine`
   (`mlx-community/whisper-large-v3-turbo` via `mlx-whisper`) as the new default,
   implementing the existing `ASREngine` Protocol. `ParakeetEngine` stays,
   reachable via `--asr-engine parakeet`, and is the automatic fallback when
   Whisper cannot load (Principle V; FR-001, FR-002, FR-009).
2. **Per-session domain biasing** — at Phase-C session start, build a domain
   context string from (a) terms mined from the question prompt, (b) a static
   engineering-term seed, and (c) a Persian-accent declaration, and pass it to
   every transcription via an additive `context` parameter on the Protocol.
   Parakeet ignores it; Whisper injects it as `initial_prompt` (FR-003, FR-004).
3. **Silero-VAD pre-segmentation** — drop silence regions before the ASR sees
   them, transcribe per speech-region, and stitch word timings back onto the
   original timeline so thinking pauses produce no phantom tokens *and* the
   existing pause/rate metrics stay correct (FR-005, FR-006).

Provenance (engine, model, domain-context hash + text, VAD settings, fallback
flag) is recorded as a single **additive top-level `asr:` key** in the report
frontmatter; `schema_version` stays **1** and the trends reader is untouched
(Principle IX; FR-007, FR-008). A reproducibility test built from the captured
kotlin-coroutines failure session is the mandatory acceptance gate (FR-010).

The three design decisions called out by the directive — (a) where domain mining
lives, (b) VAD/silence thresholds, (c) cross-session model memoization for the
5 s budget under Qwen co-residence — are resolved in
[research.md](./research.md) §(a), §(b), §(c).

## Technical Context

**Language/Version**: Python 3.12 (unchanged; `requires-python >=3.12,<3.13`).

**Package manager**: `uv`. Entry point unchanged: `uv run speakloop`.

**Primary Dependencies**: Three new third-party deps, all confined to the `asr/`
package (Principle V): `mlx-whisper` (MIT; Whisper inference on MLX),
`silero-vad` (MIT; VAD), `onnxruntime` (Silero's ONNX runtime). No other deps
are added. Existing `parakeet-mlx`, `mlx-lm`, `kokoro-mlx`, `soundfile`, `numpy`
are reused. One new model is added to the installer manifest
(`mlx-community/whisper-large-v3-turbo`, ~1.6 GB).

**Storage**: Filesystem only (unchanged). Reports stay Markdown + YAML
frontmatter under `data/sessions/`; the new `asr:` block is **additive** on
`schema_version: 1`. The new model downloads under `~/.speakloop/models/`
(Principle VI; reuses the existing resumable installer).

**Testing**: `pytest`. Live model calls remain forbidden (Development
Guidelines) — Whisper, VAD, and Parakeet are stubbed via the `ASREngine`
Protocol / monkeypatched module functions in unit tests. New fixtures: the
**kotlin-coroutines reproduction set** (recordings + hand transcript +
previous-pipeline known-bad output) backing SC-A/SC-B, and **silence-padded
clips** backing SC-C. The reproducibility gate (FR-010) is a marked pytest
(`@pytest.mark.repro`) that runs against real recordings when present and skips
with a clear message when they are absent (so CI without audio still passes,
but the gate is not green until run locally on the user's audio).

**Target Platform**: macOS arm64 (Apple Silicon, M3 Pro 18 GB) — unchanged.

**Project Type**: Single-project Python CLI under `src/speakloop/` — unchanged.

**Performance Goals**:
- A 60 s attempt transcribes end-to-end (VAD + ASR) in < 5 s on the target
  machine with Qwen-8B-4bit co-resident (SC-D). Achieved with a **warm** model:
  the Whisper model is loaded once (before attempt 1) and reused across attempts
  and replays — no per-attempt reload (research.md §c). Warm large-v3-turbo runs
  ≈270× real-time per the research brief; VAD adds tens of ms.
- First-load latency (model into memory) happens during setup, before the timed
  attempt loop, and is not counted against the per-attempt budget.

**Constraints**:
- Offline-only after install (Principle II); no cloud/remote ASR (FR-012).
- All user-facing strings English (Principle I) — including the one-line fallback
  notice (FR-009, FR-015).
- `schema_version: 1` preserved; only additive frontmatter; trends reader keeps
  working unchanged (FR-008).
- Engine-specific imports (`mlx_whisper`, `parakeet_mlx`, `silero_vad`,
  `onnxruntime`) live only inside `asr/` wrapper/helper files (Principle V,
  FR-011).
- Memory ceiling: Whisper-turbo (~1.6 GB) + Qwen-8B-4bit (~4.6 GB) + Kokoro
  (~0.2 GB) + runtime ≈ well under 18 GB (research.md §c, risk register).
- Ctrl+C during a session must not write a partial report (existing coordinator
  invariant; the engine swap does not change abort handling).

**Scale/Scope**: Single user, single machine. Changes are localized to the `asr/`
module (new files), with thin wiring edits in `sessions/coordinator.py`,
`cli/practice.py`, `installer/manifest.py`, and `feedback/frontmatter.py`
(additive `asr:` provenance). One new content-agnostic helper for domain mining.

## Constitution Check

*Gate status before Phase 0 research and re-checked after Phase 1 design:*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. English-Only UI | PASS | The only new user-facing string is the one-line fallback notice; English. |
| II. Offline-First | PASS | Whisper/VAD run locally; seed lexicon and accent declaration are in-repo constants; the new model is a one-time HuggingFace download via the existing installer, then zero network. |
| III. Privacy by Design | PASS | Audio and transcripts stay on device; no new data path. |
| IV. Modular by Design (NON-NEGOTIABLE) | PASS | All new code lives in `asr/` (single responsibility: speech→text), under the existing module + `CLAUDE.md`. Domain-context construction is a small pure helper. |
| V. Swappable Engines | PASS by design | `WhisperMLXEngine` and `ParakeetEngine` both implement the unchanged-shape `ASREngine` Protocol; the Protocol gains one **optional, additive** `context` keyword. `mlx_whisper`/`silero_vad`/`onnxruntime` imported only inside `asr/` wrapper/helper files. Engine selection + fallback live in `asr/selection.py` (inside the boundary). |
| VI. Resumable Model Downloads | PASS | New Whisper model added to the manifest; reuses the existing resumable HF downloader and validator. |
| VII. Apple Silicon Primary Target | PASS | `mlx-whisper` is MLX-native; budgets stated for M3 Pro 18 GB. |
| VIII. Easy Install for Everyone | PASS | `--help` stays model-free; `--asr-engine` is an optional power-user flag with a default. Whisper model size disclosed at consent like the others. |
| IX. Obsidian-Compatible Reports | PASS | `schema_version` stays 1; `asr:` is one additive top-level key, emitted only when present; existing readers ignore unknown keys (verified: `trends/reader.py` reads a fixed key set). |
| X. Research is Part of the Repo | PASS | Every engine/threshold choice cites `doc/research_asr_l2_accent.md`; this `research.md` records the three integration-layer decisions. `doc/research_asr.md` (the v1 Parakeet rationale) is updated with a pointer to the v2 brief and the swap (Principle X: changing an engine requires updating the research doc). |
| XI. AI-Collaborator Friendly | PASS | Work is loadable from `asr/CLAUDE.md` alone; wiring edits in other modules are one-liners documented in their `CLAUDE.md`. |
| XII. Iterative Delivery | PASS | Slices ship independently: US1 (engine + biasing) is usable before US2 (VAD) and US3 (flag + fallback). Each leaves a complete working system; Parakeet remains a working fallback throughout. |

**Non-Negotiable Constraints**: Python 3.12 ✓ · `uv` ✓ · model storage under
`~/.speakloop/models/` ✓ · YAML for any user-facing config ✓ · CLI with `rich`
only ✓ · no external services beyond the one-time model download ✓ · MIT ✓ ·
public repo ✓. New deps are MIT-licensed (mlx-whisper, silero-vad, onnxruntime);
Whisper-turbo weights are MIT (research brief F-ledger).

**Gate verdict**: PASS. No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-asr-l2-accent-accuracy/
├── plan.md              # this file
├── research.md          # Phase 0 — (a) domain mining, (b) VAD thresholds, (c) model memoization + supporting decisions
├── data-model.md        # Phase 1 — additive asr provenance + TranscriptionContext + VAD/segment entities
├── quickstart.md        # Phase 1 — run the new pipeline + the reproducibility gate locally
├── contracts/           # Phase 1
│   ├── asr-interface.py                    # extended ASREngine Protocol (+ optional context), TranscriptionContext, EngineSelection
│   ├── vad-contract.py                     # VAD segmenter contract + tunables
│   └── report-frontmatter-asr-additive.yaml # the additive `asr:` block (schema_version stays 1)
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # NOT created by /speckit-plan; produced by /speckit-tasks
```

### Source Code (repository root)

Changes are localized to the `asr/` module plus thin wiring edits. New/changed
paths only:

```text
src/speakloop/
├── asr/
│   ├── interface.py            # CHANGED: ASREngine.transcribe gains optional `context: TranscriptionContext | None = None`; add TranscriptionContext dataclass; Transcript unchanged
│   ├── whisper_mlx_engine.py   # NEW: the ONLY file allowed to `import mlx_whisper`; lazy+memoized model load; initial_prompt injection; per-speech-region transcription with timeline stitching
│   ├── parakeet_engine.py      # CHANGED: accept-and-ignore the new `context` kwarg (signature compat); no behaviour change
│   ├── vad.py                  # NEW: the ONLY file allowed to `import silero_vad`/`onnxruntime`; segment(wav) -> list[SpeechRegion]; merge gaps; thresholds from research §(b)
│   ├── domain_context.py       # NEW: pure helper — mine question terms + static seed lexicon + accent declaration -> initial_prompt string + sha256
│   ├── selection.py            # NEW: build_engine(name) -> EngineSelection; tries Whisper, falls back to Parakeet on load failure, emits the one-line notice, reports provenance (Principle V: imports both wrappers, inside the boundary)
│   ├── seed_lexicon.py         # NEW: in-repo static engineering-term seed (FR-003b)
│   ├── __init__.py             # CHANGED: re-export TranscriptionContext, EngineSelection, build_engine
│   └── CLAUDE.md               # CHANGED: document new default engine, flag, VAD, domain context, selection/fallback, the mlx_whisper/silero isolation
├── installer/
│   └── manifest.py             # CHANGED: add WHISPER_LARGE_V3_TURBO Model; Phase-C bundle includes it (Parakeet kept for fallback)
├── sessions/
│   └── coordinator.py          # CHANGED: build domain context from the Question at session start; pass `context=` into each transcribe; populate Session.asr provenance
├── cli/
│   ├── practice.py             # CHANGED: `--asr-engine` option; construct the selected engine ONCE via asr.build_engine; print fallback notice if any; inject into the loop (reuse pattern already present)
│   └── CLAUDE.md               # CHANGED: document `--asr-engine`
└── feedback/
    └── frontmatter.py          # CHANGED: additive Session.asr field; dump emits top-level `asr:` only when present; parse reads it back; schema_version stays 1

doc/
└── research_asr.md             # CHANGED: pointer to research_asr_l2_accent.md + record the default-engine swap (Principle X)

tests/
├── fixtures/
│   ├── repro_kotlin_coroutines/  # NEW: original recordings + hand transcript + previous-pipeline known-bad output (FR-010; SC-A/SC-B)
│   └── silence_clips/            # NEW: clips with 2–5 s pauses (SC-C)
├── unit/
│   └── asr/                      # NEW: domain_context mining, seed lexicon, vad merge logic (stubbed silero), selection+fallback, frontmatter asr round-trip, parakeet context-ignore
└── integration/
    ├── asr_pipeline_test.py      # NEW: VAD→Whisper(stubbed)→stitched timings; pause preserved; empty-on-all-silence
    ├── asr_fallback_test.py      # NEW: Whisper load fails → Parakeet used, notice printed, provenance records fell_back=true
    └── repro_gate_test.py        # NEW: @pytest.mark.repro acceptance gate; skips cleanly without recordings (FR-010)
```

**Structure Decision**: Keep everything inside the existing `asr/` module rather
than spawning a new top-level module — speech→text is one responsibility and the
module already owns the engine boundary (Principle IV). The new VAD and
domain-context concerns are helpers *within* that boundary, not separate
responsibilities the rest of the app needs to know about. Engine-specific imports
stay confined to `whisper_mlx_engine.py` (mlx_whisper), `vad.py`
(silero_vad/onnxruntime), and `parakeet_engine.py` (parakeet_mlx); `selection.py`
composes the wrappers but imports no third-party engine code itself
(Principle V). Wiring edits in `coordinator`/`practice`/`manifest`/`frontmatter`
are minimal and each documented in the touched module's `CLAUDE.md`.

### Phase shipping order within this feature (Iterative Delivery — Principle XII)

| Slice | Ships | User-visible outcome |
|-------|-------|----------------------|
| **US1** (P1) | `whisper_mlx_engine.py`, `domain_context.py`, `seed_lexicon.py`, manifest + coordinator + frontmatter wiring, repro fixtures + gate | The transcript reads back technical jargon correctly; provenance recorded. Validated on the kotlin-coroutines recordings (SC-A/SC-B). Default engine is now Whisper. |
| **US2** (P2) | `vad.py`, per-region transcription + timeline stitching in the Whisper engine, silence fixtures | Thinking pauses of 2–5 s produce no phantom tokens; pause/rate metrics stay correct (SC-C). |
| **US3** (P3) | `selection.py`, `--asr-engine` flag in `practice.py`, fallback notice, fallback provenance | Power users pick the engine; Whisper load failure silently? no — falls back to Parakeet with one visible line; 100% of sessions complete (SC-F). |

Each slice leaves a complete working system; Parakeet remains a working engine
throughout, so even US1 alone never regresses below the v1 baseline.

## Complexity Tracking

No constitution violations. This section is intentionally empty.
