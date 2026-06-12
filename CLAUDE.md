<!-- SPECKIT START -->
Active feature: 016-pronunciation-drills — optional read-aloud pronunciation stage. After the
  attempts, when a resource/engine SAFETY GATE permits, run a user-paced read-aloud drill block
  on the main thread while feedback runs in a BACKGROUND thread (reuses 012's analysis); the
  combined report waits for both. New `pronunciation/` module wraps a wav2vec2 CTC phoneme model
  (facebook/wav2vec2-lv-60-espeak-cv-ft, Apache-2.0, CPU) + pure-numpy CTC GOP; canonical phones
  are BUNDLED (no runtime g2p/NLTK/network). Gate = active engine (015) + live RAM (psutil): local
  Qwen → skip+explain, cloud → offer; unsafe override behind a freeze warning. Model is opt-in,
  fetched via the 007 aria2 downloader (extended: Model.weight_files + preprocessor_config.json).
  Additive only: new `pronunciation_drills` frontmatter key + report section; schema_version stays
  1; offline-by-default + grammar/coaching unchanged. Plan: specs/016-pronunciation-drills/plan.md

Prior features (one line each; details live in specs/NNN-*/):
  015-engine-aware-onboarding — `setup` persists engine + engine-aware download/doctor; `questions` group · specs/015-engine-aware-onboarding/
  014-agent-context-overhaul — code-true rewrite of root + 19 module CLAUDE.md + `.claude/rules/`; anti-rot constitution amendment (v1.1.0) · specs/014-agent-context-overhaul/
  013-grammar-json-discipline — hardened packaged grammar-prompt JSON discipline (commit b611f8d; no spec dir)
  012-responsive-session-flow — session UX (keyboard/countdown/REC) + speed (concurrent analysis, background ASR, interruptible playback, timings) · specs/012-responsive-session-flow/
  011-claude-code-engine — third engine "claude" driving the local Claude Code CLI via subprocess · specs/011-claude-code-engine/
  010-interview-loop — adaptive daily loop: follow-ups, SRS, warm-up, coverage, triage, store · specs/010-interview-loop/
  009-cloud-coaching-feedback — second OpenRouter coaching call appended to cloud reports · specs/009-cloud-coaching-feedback/
  008-openrouter-cloud-provider — opt-in `--cloud` grammar analysis via OpenRouter · specs/008-openrouter-cloud-provider/
  007-robust-model-download — aria2c parallel shard downloads with snapshot fallback · specs/007-robust-model-download/
  006-feedback-quality-reliability — free-form grammar prompt, json-repair recovery, thinking mode · specs/006-feedback-quality-reliability/
  005-context-engineering-audit — first CLAUDE.md layer audit · specs/005-context-engineering-audit/
  004-public-release-readiness — in-repo questions, path-portability audit, MIT · specs/004-public-release-readiness/
  003-asr-l2-accent-accuracy — Whisper-turbo default, Parakeet fallback, VAD + biasing · specs/003-asr-l2-accent-accuracy/
  002-post-session-debrief — LLM grammar feedback + interactive debrief · specs/002-post-session-debrief/
  001-v1-product-spec — base local interview-practice CLI · specs/001-v1-product-spec/

Constitution: .specify/memory/constitution.md (v1.1.0) — wins on any conflict.
<!-- SPECKIT END -->

# speakloop — top-level map

## Overview

speakloop is a fully local, offline English speaking-practice CLI for non-native
software engineers preparing for technical interviews. It runs three local AI models
on Apple Silicon — TTS (Kokoro-82M), ASR (Whisper-large-v3-turbo), LLM (Qwen3-14B
4-bit) — to drive a listen → attempt (4/3/2) → feedback loop with SRS scheduling,
written as Obsidian-compatible Markdown reports. After the initial model download the
default path makes zero network calls; `--cloud`/`--engine` opt into remote analysis.

## Tech stack

From `pyproject.toml`, confirmed against imports.

- **Python 3.12** — pinned `>=3.12,<3.13` (`pyproject.toml:7`). **`uv`** is the only
  package manager; run everything via `uv run`.
- **CLI/UI**: `typer` ≥0.12, `rich` ≥13.7 (CLI only — no GUI, constitution constraint).
- **Config/data**: `pyyaml` ≥6.0, `python-frontmatter`, `numpy` ≥1.26, `json-repair` ≥0.30.
- **Audio**: `sounddevice` ≥0.4, `soundfile` ≥0.12, `scipy` ≥1.13 (resample fallback,
  `src/speakloop/audio/playback.py:66`).
- **Download**: `huggingface_hub` ≥0.24 (resumable).
- **Engine packages** (each imported function-local in exactly ONE wrapper file):
  `mlx-whisper`, `parakeet-mlx`, `silero-vad`, `mlx-lm`, `kokoro-mlx`.
- **`onnxruntime` ≥1.20**: a load-bearing direct dependency — `asr/vad.py:97` loads
  silero with `onnx=True`, and `silero-vad` ≥6 declares `onnxruntime` only under its
  onnx extras. Removing the declaration breaks the first live VAD call.
- **`torchaudio<2.9`** (`pyproject.toml:38`) — capped; see Traps.
- **`transformers` ≥4.34 + `torch` (≈2.8, via torchaudio) + `psutil` ≥5.9** (016): the
  optional pronunciation scorer wraps a wav2vec2 CTC model (transformers/torch, function-local
  in `pronunciation/wav2vec2_engine.py`, CPU) and the safety gate reads live RAM via psutil.

## Layout

Twenty single-responsibility modules under `src/speakloop/`, each with its own
CLAUDE.md (constitution Principle IV). Edges below are from an import scan
(`rg -o "from speakloop\.(\w+)" src/speakloop/<mod>/`), regenerated 2026-06-12.

| Module | Responsibility | Depends on (internal) |
|--------|----------------|-----------------------|
| `config/` | Paths, Q&A precedence, `loop.yaml` parse + `engine:` writer (015) | — (leaf) |
| `content/` | Q&A YAML loader + schema + starter template (`content/questions.yaml`) | — (leaf) |
| `trends/` | Cross-session dashboard + per-pattern series | — (leaf) |
| `installer/` | Model manifest, consent, resumable download, validation | config |
| `asr/` | ASR wrapper (owns `mlx_whisper`, `silero_vad`, `parakeet_mlx`) | installer |
| `llm/` | LLM engines (owns `mlx_lm`; OpenRouter; Claude Code CLI) | config, installer |
| `tts/` | TTS wrapper (owns `kokoro_mlx`) + size-capped clip cache | config, installer |
| `metrics/` | Per-attempt fluency metrics (deterministic, no LLM) | asr |
| `audio/` | Playback (interruptible), recording, device probing | sessions |
| `feedback/` | Frontmatter, atomic writer, report builder, grammar analyzer, coach, timings | asr, config, llm |
| `debrief/` | Post-session interactive debrief | feedback, tts |
| `triage/` | Hallucination filter, mishearing, artifact consistency | asr, config, feedback, llm |
| `coverage/` | Key points + coverage scoring + content errors | asr, config, feedback, llm |
| `interviewer/` | Grounded follow-up generation | asr, config, feedback, llm |
| `warmup/` | Warm-up drill generation + deterministic judge | config, feedback, llm |
| `srs/` | Grade + interval ladder + due queue (pure logic) | store |
| `store/` | Derived JSON store, rebuildable cache | feedback |
| `pronunciation/` | Read-aloud scorer (owns `torch`+`transformers`), pure-numpy CTC GOP, engine/RAM safety gate, bundled drill bank (015) | installer |
| `sessions/` | 4/3/2 coordinator, keyboard, session UI, analysis executor, timer, abort, drill block (016) | asr, audio, config, content, coverage, feedback, metrics, pronunciation, srs, store, trends, triage, warmup |
| `cli/` | `practice`, `setup`, `questions`, `doctor`, `trends`, `today`, `rebuild`, `resume` | all 17 others except debrief at module level (debrief + pronunciation imported function-local) |

## Commands

```bash
uv run speakloop --help     # must work with NO models downloaded
uv run speakloop setup [--engine local|openrouter|claude] [--no-download]  # persist engine + download only what it needs (015)
uv run speakloop doctor     # environment + model health, engine-aware (exit 0 when healthy)
uv run speakloop practice [--listen-only] [--cloud] [--engine local|openrouter|claude] [--timings] [--drills/--no-drills]  # --drills: read-aloud pronunciation drills during the feedback wait, engine/RAM-gated (016)
uv run speakloop questions validate [PATH] | template | where  # author/validate your own Q&A (015)
uv run speakloop today | resume | rebuild | trends
uv run pytest               # full suite — re-measure pass count after each feature
uv run pytest -m live_asr   # real silero+torchaudio smoke — run when touching torchaudio
uv run pytest tests/integration/test_path_portability_audit.py  # no personal paths
uv run pytest tests/integration/test_context_file_budget.py     # CLAUDE.md ≤200 lines
```

`ruff` is configured (`pyproject.toml [tool.ruff]`) but `ruff check .` has known
pre-existing findings — not a passing gate.

## Conventions

- English-only user-facing output (constitution I).
- Engine imports are function-local, each engine package in exactly one wrapper file,
  so `--help` loads no models (constitution V + VIII). Replacing an engine touches
  exactly one file.
- Report `schema_version` stays 1 (`src/speakloop/feedback/frontmatter.py:11`); new
  frontmatter keys are additive and optional — never bump, never make required.
- Reports: Obsidian-compatible Markdown in `data/sessions/`, named
  `YYYY-MM-DD-<question_id>.md` with `-2`/`-3` collision suffixes
  (`feedback/markdown_writer.py:42`).
- User config is YAML only; `loop.yaml` keys are all optional with silent defaults
  (see `src/speakloop/config/CLAUDE.md` for the key table).
- Conventional Commits (`feat:`, `fix:`, `docs:`, …).
- Engine changes update the matching `doc/research_*.md` (constitution X).

## Traps

1. **Don't bump `torchaudio` past `<2.9`** (`pyproject.toml:38`) without
   `uv run pytest -m live_asr`: ≥2.11 moves decoding to unbundled `torchcodec` and
   crashes the first live VAD call (commit `21dfb86`).
2. **A module-level engine import breaks `--help`.**
   `tests/integration/test_help_without_models.py:27` asserts importing the CLI loads
   none of the engine packages (`mlx_whisper`, `silero_vad`, `parakeet_mlx`, `mlx_lm`,
   `kokoro_mlx`, plus `torch`/`transformers` from 016);
   `tests/unit/asr/test_engine_import_isolation.py` pins each to its single wrapper file
   (`torch`/`transformers` → `pronunciation/wav2vec2_engine.py`).
3. **Serial and concurrent analysis must produce a byte-identical report** — rule
   owned by `src/speakloop/sessions/CLAUDE.md`; gate:
   `tests/integration/test_analysis_equivalence.py`.
4. **The Claude Code engine has a strict invocation contract** (subscription billing,
   env stripping, `is_error` keying) — owned by `src/speakloop/llm/CLAUDE.md`.
5. **Grammar JSON recovery contract** (json-repair ladder, no hand-rolled regex,
   bounded regenerate) — owned by `src/speakloop/feedback/CLAUDE.md`.
6. **Raw keyboard input is NOT fully consolidated**: `sessions/keyboard.py` is the
   session-path reader (KeyReader Protocol + Raw/Null/Fake), but the pre-session
   listen loop keeps its own `_cbreak_read` (`src/speakloop/cli/practice.py:118`) and
   the debrief menu its own `_cbreak_read_key` (`src/speakloop/debrief/menu.py:34`).
7. **No personal absolute paths** (`/Users/...`) in any committed file —
   `tests/integration/test_path_portability_audit.py` fails otherwise.
8. **Q&A file precedence** is owned by `src/speakloop/config/CLAUDE.md`
   (`resolve_qa_file`, `config/paths.py:103`) — no auto-copy to `~/.speakloop/`.

## Never do

- Add a network call to the default (local) path after model download (constitution II).
- Import an engine package at module top level, or from more than one file (constitution V).
- Bump report `schema_version` or make a frontmatter key required.
- Ship non-English user-facing strings; introduce a GUI, non-YAML user config, or a
  `pip install` workflow (constitution I + constraints).
- Edit `.specify/memory/constitution.md` from a normal feature (governance amendment only).
- Edit `specs/001`–`013` artifacts — they are immutable history; fix forward in context files.
- Land a behavior-changing commit without updating the owning context file (CLAUDE.md /
  rules file) in the same commit — constitution v1.1.0 anti-rot rule.
- Touch the real `claude` binary, microphone, keyboard, or live models from tests —
  owned by `.claude/rules/testing.md`.

## Maintenance

Anti-rot: every behavior-changing commit updates the owning context file in the same
commit (constitution v1.1.0). `tests/integration/test_context_file_budget.py` enforces
≤200 lines per CLAUDE.md. On each new `specs/NNN-*` feature: update the SPECKIT block
(active ≤10 lines, prior features one line each) and re-check the module table edges.

## Pointers

- Per-module guidance: `src/speakloop/<module>/CLAUDE.md` (loads on demand).
- Path-scoped rules: `.claude/rules/testing.md` (tests/**),
  `.claude/rules/llm-calls.md` (LLM-caller modules).
- Specs: `specs/001`–`specs/016` (plan.md · spec.md per feature).
- Engine research: `doc/research_{tts,asr,llm,methodology,pronunciation}.md`; context
  engineering: `doc/research_context_engineering.md`.
- Governance: `.specify/memory/constitution.md` (v1.1.0) — wins on any conflict.
