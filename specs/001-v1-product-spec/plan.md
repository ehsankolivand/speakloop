# Implementation Plan: speakloop v1 — local English interview-practice CLI

**Branch**: `001-v1-product-spec` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-v1-product-spec/spec.md`

## Summary

speakloop is a CLI tool that runs three local AI engines (TTS, ASR, LLM) on Apple Silicon to deliver a structured interview-practice loop: listen to a natively-spoken question and ideal answer, attempt the answer three times under 4/3/2-minute pressure, then receive an evidence-based Markdown feedback report viewable in Obsidian.

Engine choices are pre-resolved by the in-repo research documents and are NOT re-litigated here:

- **TTS**: Kokoro-82M via `kokoro-mlx` (Apache 2.0, native MLX, IPA override via Misaki). Fallback engine candidate per `doc/research_tts.md`: Piper. — See `doc/research_tts.md`.
- **ASR**: Parakeet-TDT-0.6b-v3 via `parakeet-mlx` (RNN-T/TDT — does **not** hallucinate on silence; ~2 GB peak RAM; native MLX). Fallback: faster-whisper. — See `doc/research_asr.md`.
- **LLM**: Qwen3-8B (MLX 4-bit) via `mlx_lm` (Apache 2.0; thinking suppressed via `apply_chat_template(enable_thinking=False)` plus a defensive `<think>` regex strip — sidesteps the documented `<think>`-leak bug; ~4.62 GB on disk). The `mlx-community/Qwen3.5-9B-MLX-4bit` repo turned out to be a vision-language model incompatible with `mlx_lm.load()` — see the rationale comment in `src/speakloop/installer/manifest.py`. Fallback: Llama 3.1 8B Instruct. — See `doc/research_llm.md`.

Implementation is sequenced into three end-user-facing phases per the user's input, each shipping a complete working system: **Phase A** (TTS-only listening practice), **Phase B** (record + transcribe + fluency metrics), **Phase C** (LLM-generated feedback report + trends dashboard).

## Technical Context

**Language/Version**: Python 3.12 (3.11+ per Constitution Non-Negotiable Constraints; 3.13 has documented `spacy`/`pydantic` conflicts in the Kokoro stack per `doc/research_tts.md` p. 48, so pin to 3.12).

**Package manager**: `uv` (Constitution-mandated). Project metadata in `pyproject.toml`. The single user-facing entrypoint is `uv run speakloop`.

**Primary Dependencies** (grouped by phase):

- **Phase A**: `kokoro-mlx` (TTS), `huggingface_hub` (resumable download primitives), `pyyaml` (Q&A loader), `sounddevice` + `soundfile` (audio playback), `rich` (CLI rendering — Constitution Non-Negotiable), `typer` (argument parser — pairs with `rich`; standard-library `argparse` is a fallback if `typer` adds unwanted weight).
- **Phase B (additional)**: `parakeet-mlx` (ASR), `sounddevice` already covers recording, `numpy` (already a transitive dep of every audio package above).
- **Phase C (additional)**: `mlx-lm` (LLM driver), `python-frontmatter` (parse Markdown reports for trends — alternative: hand-roll a 30-line YAML-block reader).
- **Installed but unused** (deferred cleanup): `readchar>=4.2.2`. The prior listen-loop keypress path used `readchar`; the as-built 2-tier tty implementation in `cli/practice.py` reads via `termios`+`tty.setcbreak` directly, leaving `readchar` resident but unreferenced.

**Storage**: Filesystem only. Models under `~/.speakloop/models/` (Constitution Non-Negotiable). Session reports under `data/sessions/` (Constitution Principle IX). Q&A YAML at `~/.speakloop/qa.yaml` with starter file `src/speakloop/content/starter.yaml` shipped in-repo and copied on first run if no user file exists.

**Testing**: `pytest`. Engine-wrapping modules use cached fixture WAVs/transcripts committed to `tests/fixtures/` — **live model calls in tests are forbidden** (Constitution Development Guidelines).

**Target Platform**: macOS arm64 (Apple Silicon). M-series, MLX-backed (Constitution Principle VII).

**Project Type**: Single-project Python CLI. Repository root `pyproject.toml`; source under `src/speakloop/`.

**Performance Goals**: Reflects measurable success criteria in `spec.md`. Specifically:

- `speakloop --help` returns in ≤ 2 s with no models present (SC-006).
- Report produced within 60 s of attempt 3 ending (SC-003).
- Resume interrupted download re-fetches ≤ 1 % of completed bytes (SC-002).
- Health-check covers every breakable precondition in a single run (SC-007).

**Constraints**:

- Offline-only after model install (Constitution Principle II / FR-023, FR-037).
- No telemetry, no auto-update (Constitution Principles II/III).
- All user-facing strings in English (Constitution Principle I / FR-036).
- Ctrl+C MUST NOT leave a partial report (FR-016, SC-005).
- The system is async by design — no real-time spoken dialogue (spec Assumptions).

**Scale/Scope**: Single user on a single machine. Tens to low hundreds of Q&A entries. Hundreds of session reports in `data/sessions/` over a year of daily use.

## Constitution Check

*Gate status before Phase 0 research:*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. English-Only UI | PASS | All user-facing strings English only (FR-036). No localization layer planned. |
| II. Offline-First | PASS | Only network calls are the first-run model downloads (FR-019..FR-023). |
| III. Privacy by Design | PASS | All artifacts on local disk only (FR-035). No upload path exists. |
| IV. Modular by Design (NON-NEGOTIABLE) | PASS by design | The project structure below splits one concern per module, each with its own `CLAUDE.md`. |
| V. Swappable Engines | PASS by design | Each of `tts/`, `asr/`, `llm/` exposes a Python `Protocol` interface; only `*_engine.py` files import engine-specific packages. |
| VI. Resumable Model Downloads | PASS | `huggingface_hub.snapshot_download` provides byte-range resume (FR-021). |
| VII. Apple Silicon Primary Target | PASS | All three chosen engines have native MLX paths per the research docs. |
| VIII. Easy Install for Everyone | PASS | `uv run speakloop` flow with explicit consent gate (FR-019); `--help` works model-free (FR-018). |
| IX. Obsidian-Compatible Reports | PASS | Markdown + YAML frontmatter under `data/sessions/` with versioned schema (FR-010, FR-011, FR-015). |
| X. Research is Part of the Repo | PASS | All four research files (`research_tts.md`, `research_asr.md`, `research_llm.md`, `research_methodology.md`) are present in `doc/`. The previously-tracked exception (methodology doc missing) was resolved before Phase C work began; see **Complexity Tracking** below for the resolution note. |
| XI. AI-Collaborator Friendly | PASS by design | Top-level `CLAUDE.md` is the map; every module ships its own `CLAUDE.md`. |
| XII. Iterative Delivery | PASS | The three-phase shipping order below makes the TTS-only MVP usable before B and C land. |

**Non-Negotiable Constraints**: Python 3.12 ✓ · `uv` ✓ · `~/.speakloop/models/` ✓ · YAML config ✓ · CLI with `rich` ✓ · No external services beyond model download ✓ · MIT license (declared in `pyproject.toml`) ✓ · Public GitHub repo ✓.

**Gate verdict**: PASS with one tracked exception (Principle X) that does not block Phase A or Phase B. Re-evaluated unchanged after Phase 1 design.

## Project Structure

### Documentation (this feature)

```text
specs/001-v1-product-spec/
├── plan.md              # this file
├── research.md          # Phase 0 — integration-layer decisions (engine choices cite doc/research_*.md)
├── data-model.md        # Phase 1 — entities + frontmatter schema v1
├── quickstart.md        # Phase 1 — clone → uv run speakloop on first machine
├── contracts/           # Phase 1
│   ├── cli-commands.md          # subcommand surface (practice, trends, doctor, --help)
│   ├── tts-interface.py         # Python Protocol the TTS module exposes
│   ├── asr-interface.py         # Python Protocol the ASR module exposes
│   ├── llm-interface.py         # Python Protocol the LLM module exposes
│   ├── content-schema.yaml      # Q&A YAML schema
│   └── report-frontmatter.yaml  # session-report YAML frontmatter schema (schema_version: 1)
├── checklists/
│   └── requirements.md  # already exists, generated by /speckit-specify
└── tasks.md             # NOT created by /speckit-plan; produced by /speckit-tasks
```

### Source Code (repository root)

The chosen layout is single-project Python under `src/`, deliberately split into many small modules so each has its own `CLAUDE.md` and a single responsibility (Constitution Principles IV, XI). Engine-specific imports are confined to one file per engine (Principle V).

```text
src/speakloop/
├── __init__.py
├── config/                       # paths and constants (one source of truth)
│   ├── __init__.py
│   ├── paths.py                  # ~/.speakloop/models/, data/sessions/, qa.yaml
│   └── CLAUDE.md
├── cli/                          # argument parsing + top-level command dispatch
│   ├── __init__.py
│   ├── main.py                   # `speakloop` entry, --help, dispatch
│   ├── practice.py               # `speakloop practice`
│   ├── trends.py                 # `speakloop trends`        (Phase C)
│   ├── doctor.py                 # `speakloop doctor`
│   └── CLAUDE.md
├── installer/                    # model presence, consent, resumable download
│   ├── __init__.py
│   ├── manifest.py               # per-phase model list (TTS only in A; +ASR in B; +LLM in C)
│   ├── consent.py                # rich-rendered consent prompt + size disclosure
│   ├── downloader.py             # wraps huggingface_hub snapshot_download
│   ├── validator.py              # size/checksum validation (FR-022)
│   └── CLAUDE.md
├── content/                      # Q&A YAML loading + validation
│   ├── __init__.py
│   ├── loader.py
│   ├── schema.py                 # dataclass + validation; matches contracts/content-schema.yaml
│   ├── starter.yaml              # ships in-repo, copied to ~/.speakloop/qa.yaml on first run
│   └── CLAUDE.md
├── tts/                          # TTS engine wrapper
│   ├── __init__.py
│   ├── interface.py              # class TTSEngine(Protocol) — STABLE
│   ├── kokoro_engine.py          # ONLY file that imports kokoro_mlx / mlx_audio
│   ├── cache.py                  # cache synthesized clips by sha256(voice|text)
│   └── CLAUDE.md
├── audio/                        # local audio I/O — recording and playback
│   ├── __init__.py
│   ├── playback.py               # Phase A
│   ├── recorder.py               # Phase B
│   ├── devices.py                # input/output probing for doctor
│   └── CLAUDE.md
├── asr/                          # ASR engine wrapper                              [Phase B]
│   ├── __init__.py
│   ├── interface.py              # class ASREngine(Protocol) — STABLE
│   ├── parakeet_engine.py        # ONLY file that imports parakeet_mlx
│   └── CLAUDE.md
├── metrics/                      # per-attempt fluency metric computation         [Phase B]
│   ├── __init__.py
│   ├── speech_rate.py            # words per minute, including filler exclusion
│   ├── pauses.py                 # pause-rate distribution
│   ├── fillers.py                # filler-word density ("uh", "um", …)
│   ├── self_corrections.py       # restart/repair detection
│   └── CLAUDE.md
├── llm/                          # LLM engine wrapper                              [Phase C]
│   ├── __init__.py
│   ├── interface.py              # class LLMEngine(Protocol) — STABLE
│   ├── qwen_engine.py            # ONLY file that imports mlx_lm
│   └── CLAUDE.md
├── feedback/                     # report assembly                                 [Phase C]
│   ├── __init__.py
│   ├── grammar_analyzer.py       # LLM-driven grammar-pattern detection (FR-013)
│   ├── frontmatter.py            # versioned YAML schema serializer
│   ├── markdown_writer.py        # atomic write — temp file + rename (supports FR-016)
│   ├── report_builder.py         # composes frontmatter + body sections
│   └── CLAUDE.md
├── sessions/                     # the orchestrator of the 4/3/2 loop
│   ├── __init__.py
│   ├── coordinator.py            # ties TTS+audio+ASR+metrics+feedback together
│   ├── timer.py                  # rich countdown; per-attempt budgets
│   ├── abort.py                  # Ctrl+C / signal handling; cleanup invariants
│   └── CLAUDE.md
├── trends/                       # progress dashboard                              [Phase C]
│   ├── __init__.py
│   ├── reader.py                 # parse Markdown frontmatter back into structures
│   ├── aggregator.py             # per-metric time series + grammar-pattern counts
│   ├── renderer.py               # rich tables / sparklines in the terminal
│   └── CLAUDE.md
└── (no other top-level modules in v1)

tests/
├── fixtures/                     # committed cached fixtures (Constitution Dev Guidelines)
│   ├── wav/
│   │   ├── tts/                  # tiny pre-synthesized clips for tts tests
│   │   └── recordings/           # tiny pre-recorded attempt WAVs for asr/metrics tests
│   ├── transcripts/              # pre-transcribed text for metrics + feedback tests
│   └── qa/                       # YAML fixtures (valid, invalid, missing-field)
├── unit/
│   ├── content/
│   ├── metrics/
│   ├── feedback/
│   ├── trends/
│   ├── installer/
│   └── tts_cache_test.py
├── integration/
│   ├── phase_a_listen_test.py    # cli → tts → playback (uses fixture WAVs, no live model)
│   ├── phase_b_attempt_test.py   # adds recording + asr; fixture WAVs in, transcripts compared
│   └── phase_c_report_test.py    # full session → markdown report; fixture LLM stub
└── conftest.py

doc/                              # already in repo
├── research_tts.md
├── research_asr.md
├── research_llm.md
└── research_methodology.md       # NOT YET PRESENT — see Complexity Tracking

data/sessions/                    # gitignored; populated at runtime
└── .gitkeep                      # keeps the dir in-repo for first-run

CLAUDE.md                         # top-level map; lists every module and links to its CLAUDE.md
pyproject.toml                    # uv-managed; entrypoint speakloop = speakloop.cli.main:app
README.md
LICENSE                           # MIT
```

**Structure Decision**: Single-project Python CLI under `src/speakloop/`. Module boundaries are intentionally fine-grained — twelve modules at the first level, each with `__init__.py`, a `CLAUDE.md`, and ≤ ~250 LOC of Python in v1. This satisfies Principle IV (single responsibility) and Principle XI (each module is loadable by an AI agent without the rest). Engine-specific imports are scoped to a single file per engine (`kokoro_engine.py`, `parakeet_engine.py`, `qwen_engine.py`) — swapping an engine in the future touches exactly that one file plus, at worst, the module's `manifest.py` entry in `installer/` (Principle V).

### Phase shipping order (Iterative Delivery — Principle XII)

| Phase | Ships these modules | What the user can do at the end of the phase |
|-------|--------------------|-----------------------------------------------|
| **A** | `config`, `cli` (main + practice listen-only + doctor), `installer`, `content`, `tts`, `audio` (playback only) | Clone → consent to TTS model → `speakloop practice` → pick a question → hear question + ideal answer → replay → exit. Story 1, Story 3, Story 5, Story 6 deliver fully. Doctor reports what is present and what is missing for B/C. |
| **B** | `audio` (recorder added), `asr`, `metrics`, `sessions` (coordinator extended to full 4/3/2), `cli/practice.py` extended | Full 4/3/2 loop runs; recorded attempts get transcribed; per-attempt fluency metrics computed; an interim Markdown report with transcripts + metrics is written under `data/sessions/` (no LLM grammar feedback yet — body section flagged "feedback pending Phase C"). Story 2 partially delivered. |
| **C** | `llm`, `feedback`, `trends`, `cli/trends.py` | Reports gain the LLM-driven grammar-pattern findings with evidence quotes; `speakloop trends` command lights up. Stories 2 and 4 fully delivered; v1 complete. |

**Each phase is a complete working system, not a partial scaffold.** A user who installs after only Phase A merges still has a useful shadowing-practice tool. The B-phase report format is forward-compatible with C: the body just gains sections.

## Complexity Tracking

| Violation | Resolution |
|-----------|------------|
| (Historical) `doc/research_methodology.md` was not present on disk at planning time, violating Constitution Principle X. | **Resolved.** The methodology document was authored before Phase C task generation began; `feedback/grammar_analyzer.py` and the `metrics/` module are specified against it. All seed-5 grammar patterns (FR-013a) and the 250 ms pause threshold (FR-012b) trace back to this document. |

No outstanding violations.

## Notes on user input

The user's directive — "treat the research documents in `doc/` as authoritative; do not re-research what is settled" — is reflected in `research.md`: that file documents only the **integration-layer** decisions (audio I/O library, CLI library, HF download primitives, frontmatter parser, testing setup). Engine selection sections cite the existing `doc/research_*.md` files without re-deriving their conclusions.

The user's three-phase shipping directive is encoded in the **Phase shipping order** table above and is the basis for the per-phase task generation that `/speckit-tasks` will produce.

The user's "many small modules, each with its own CLAUDE.md" directive is reflected in the twelve first-level modules under `src/speakloop/`, each of which has a `CLAUDE.md` entry in the tree. Engine wrappers (`tts`, `asr`, `llm`) hide engine-specific imports in a single file per engine, satisfying Principle V.
