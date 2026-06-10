<!-- SPECKIT START -->
Active feature: 011-claude-code-engine — add a THIRD analysis engine "claude" behind
  the existing injected `LLMEngine` Protocol, driving the learner's locally installed,
  logged-in Claude Code CLI via stdlib `subprocess` (ZERO new deps;
  `llm/claude_code_engine.py` is the ONLY file that spawns the `claude` subprocess —
  Principle V, mirroring `openrouter_engine.py`). Engine selection becomes
  `--engine local|openrouter|claude` on `practice`/`resume`, with `--cloud` PRESERVED
  as an alias for `--engine openrouter`, plus a `loop.yaml` `engine:` default. Every
  analysis call (follow-ups, key points, coverage+content errors, mishearing,
  consistency, drill, grammar, coach) routes through Claude Code; ZERO
  call-site/prompt/schema changes (reuses the cloud prompt files + the existing
  `grammar_analyzer._extract_json` recovery ladder). SUBSCRIPTION-BILLED: the engine
  STRIPS `ANTHROPIC_API_KEY` + related override vars from the subprocess env so billing
  never silently switches to pay-per-token. Invocation pinned to observed
  `claude 2.1.170`: `--print --output-format json --model <alias> --safe-mode
  --tools "" --no-session-persistence --system-prompt`, user prompt on stdin; key off
  envelope `is_error` (NOT `subtype`), output text in `.result` (fences stripped by the
  ladder). `--safe-mode` NOT `--bare` (`--bare` would force `ANTHROPIC_API_KEY` auth,
  which we strip). Failures map to `LLMEngineError` subclasses (not_installed / auth /
  rate_limited / timeout / bad_output) → existing `analysis_pending` degradation
  unchanged, NO auto-fallback to local. `doctor` gains Claude Code rows (binary /
  version / auth via the credit-free `claude auth status --json` / default engine). P2:
  static call-site→tier→model map (fast=haiku for mishearing+drills, strong=sonnet for
  the rest), overridable via `loop.yaml` `claude_fast_model`/`claude_strong_model`;
  wired by one engine instance per tier (`_build_runners` gains an optional
  `fast_engine` kwarg defaulting to the main engine). Tests use an INJECTED FAKE RUNNER
  only — no automated test ever spawns the real `claude`. Local Qwen stays the default;
  default path stays byte-identical + offline; report `schema_version` stays 1.

Plan: specs/011-claude-code-engine/plan.md
Spec: specs/011-claude-code-engine/spec.md
  (research.md · data-model.md · contracts/{engine-interface,cli-commands,loop-config}.md)

Prior feature: 010-interview-loop — adaptive daily loop: due-question selection →
  warm-up drill → question + 4/3/2 attempts → 1–2 spoken follow-ups → richer report.
  P1 follow-ups · P2 cross-session memory + SRS + warm-up · P3 content-coverage scoring
  · P4 trustworthy pipeline (hallucination triage, mishearing, consistency) · P5
  behavioral/STAR + hypothetical types. Each new LLM step is a NEW caller of `LLMEngine`
  behind `--cloud` routing (no new engine client); additive optional frontmatter,
  `schema_version` 1; one rebuildable derived JSON store (`speakloop rebuild`). New
  modules: interviewer/ triage/ coverage/ srs/ warmup/ store/; new CLI: today, rebuild,
  resume. Plan: specs/010-interview-loop/plan.md · Spec: specs/010-interview-loop/spec.md

Prior feature: 009-cloud-coaching-feedback — richer COACHING layer for cloud mode
  (`practice --cloud`): a SECOND OpenRouter call after the grammar analyzer
  (corrected answer + focused teaching + paste-ready Anki cards), reusing the same
  engine; FREE-FORM Markdown appended grammar→coaching→transcripts; own prompt file
  `~/.speakloop/openrouter_coach_prompt.txt`; `coaching` body-only, `coach_error`
  additive; degrades gracefully; schema_version 1; local mode byte-identical.
  Plan: specs/009-cloud-coaching-feedback/plan.md · Spec: specs/009-cloud-coaching-feedback/spec.md

Prior feature: 008-openrouter-cloud-provider — OPT-IN cloud mode
  (`speakloop practice --cloud`) routing ONLY the Phase-C grammar/coherence step
  to an OpenRouter model instead of the local Qwen3-14B weights (for users who
  can't fit the local LLM in RAM). Speech (Kokoro) + transcription
  (Whisper/Parakeet) stay local. New `OpenRouterEngine` implements the existing
  `LLMEngine` Protocol (Principle V) so `feedback/grammar_analyzer.py` is REUSED
  via one additive `analyze(..., system_prompt=None)` param; transport = stdlib
  `urllib` (no new dep). Token env `OPENROUTER_API_KEY` > `~/.speakloop/openrouter_token`
  (0600); model id `model:` in `~/.speakloop/openrouter.yaml` > default
  `qwen/qwen3.7-max`; cloud prompt `~/.speakloop/openrouter_prompt.txt`. Preflight
  `GET /key` fails fast; transient failures degrade through `phase_c_error`.
  Default (no `--cloud`) byte-for-byte unchanged + offline.
  Plan: specs/008-openrouter-cloud-provider/plan.md · Spec: specs/008-openrouter-cloud-provider/spec.md

Prior feature: 007-robust-model-download — resilient model downloads: Python port
  of `download_aria.sh` (aria2c parallel shards + curl metadata + caffeinate),
  env `$HF_TOKEN` > `~/.cache/huggingface/token` > anon, auto-fallback to
  snapshot_download when aria2 absent. Validation/consent/manifest/schema_version
  unchanged. Plan: specs/007-robust-model-download/plan.md

Prior feature: 006-feedback-quality-reliability — made the existing AI-derived
  feedback (grammar suggestions, cross-attempt narrative, single top-priority)
  reliably higher-quality. LLM is Qwen3-14B at MLX 4-bit; report format &
  schema_version stay 1; fully offline; Persian-L1 catalog retired (free-form
  grammar prompt); JSON recovery via `json-repair` + one bounded regenerate;
  thinking mode ON, leading `<think>...</think>` stripped at wrapper boundary.
  Plan: specs/006-feedback-quality-reliability/plan.md · Spec: specs/006-feedback-quality-reliability/spec.md

Prior feature: 005-context-engineering-audit — audited & rewrote the CLAUDE.md layer
  (root + 13 module files) as a code-true deliverable; launch footprint ≤ 6000 tokens.
  Plan: specs/005-context-engineering-audit/plan.md · Spec: specs/005-context-engineering-audit/spec.md

Prior feature: 004-public-release-readiness — cloneable & runnable by a stranger.
  Default questions ship in-repo at `content/questions.yaml`; `~/.speakloop/qa.yaml`
  is an opt-in override (precedence: --qa-file → home override → repo default).
  Adds a stdlib+git path-portability audit (pytest, < 2 s). No new dependency;
  report schema_version stays 1; MIT LICENSE present.
  Plan: specs/004-public-release-readiness/plan.md · Spec: specs/004-public-release-readiness/spec.md

Prior feature: 003-asr-l2-accent-accuracy — faithful transcripts on Persian-L1
  accented technical English. Default ASR Whisper-large-v3-turbo (mlx-whisper),
  Parakeet-TDT via `--asr-engine parakeet` + automatic fallback; per-session domain
  biasing + Silero-VAD; additive `asr:` frontmatter key (schema_version stays 1).
  Plan: specs/003-asr-l2-accent-accuracy/plan.md · Spec: specs/003-asr-l2-accent-accuracy/spec.md

Prior feature: 002-post-session-debrief — educational LLM grammar feedback
  (originally Persian-L1 catalog; the catalog was retired in May 2026 by 006
  in favour of a free-form prompt) + in-terminal interactive debrief.
  Plan: specs/002-post-session-debrief/plan.md · Spec: specs/002-post-session-debrief/spec.md
  New module: src/speakloop/debrief/ (render + audio + menu).

Base feature: speakloop v1 — local English interview-practice CLI.
  Plan: specs/001-v1-product-spec/plan.md · Spec: specs/001-v1-product-spec/spec.md

Engine selections cite the in-repo research documents:
  doc/research_tts.md (Kokoro-82M),
  doc/research_asr.md (Parakeet-TDT-0.6b-v3),
  doc/research_llm.md (Qwen3-14B 4-bit — the original survey recommended
    Qwen3.5-9B but that HF repo was a VLM incompatible with `mlx_lm.load()`; the
    code first shipped Qwen3-8B-4bit, then Qwen3-14B-6bit, and now Qwen3-14B-4bit
    after the 6-bit variant exceeded the M3 Pro 18 GB resident-RAM budget. See
    `doc/research_llm.md` Update — 2026-05-25 and `installer/manifest.py`
    rationale comment).

Constitution: .specify/memory/constitution.md (v1.0.0).
Shipping order is three phases (A: listen-only, B: attempts + metrics, C: LLM feedback + trends);
each phase is a complete working system per Principle XII.
<!-- SPECKIT END -->

<!-- Human-authored map below. Anatomy (FR-010): overview · tech-stack · layout ·
commands · conventions · maintenance · traps · never-do · pointers. Code is the
source of truth; the constitution wins on any documentation conflict. -->

# speakloop — top-level map

## Overview

speakloop is a fully local, offline English speaking-practice CLI for non-native
software engineers preparing for technical interviews. It runs three local AI models
on Apple Silicon — TTS (Kokoro-82M), ASR (Whisper-large-v3-turbo), LLM (Qwen3-14B
4-bit) — to drive a listen → attempt (4/3/2) → feedback loop, written as Obsidian-
compatible Markdown reports. After the initial model download it makes zero network
calls (Constitution Principles II, III).

## Tech stack

Derived from `pyproject.toml`, confirmed against actual imports.

- **Python 3.12** — pinned `requires-python = ">=3.12,<3.13"` (`pyproject.toml:7`).
- **`uv`** — the only package manager (no `pip` workflows). Run everything via `uv run`.
- **CLI / UI**: `typer` (≥0.12), `rich` (≥13.7) — CLI only, no GUI (constitution constraint).
- **Config / data**: `pyyaml` (≥6.0, YAML user config), `python-frontmatter` (report YAML), `numpy` (≥1.26).
- **Audio**: `sounddevice` (≥0.4), `soundfile` (≥0.12).
- **Models / download**: `huggingface_hub` (≥0.24, resumable).
- **Engine packages** (each imported function-local in exactly ONE wrapper — Principle V):
  `mlx-whisper` (ASR), `parakeet-mlx` (ASR fallback), `silero-vad` (VAD), `mlx-lm` (LLM),
  `kokoro-mlx` (TTS).
- **`onnxruntime` (≥1.20)**: declared to pin the version, but **no direct import** in `src/` —
  it is transitive via `silero-vad` (divergence D-1).
- **`torchaudio<2.9`** (capped): ≥2.11 moves decoding to the unbundled `torchcodec` and crashes
  the first live VAD call — see Traps.

## Layout

Thirteen single-responsibility modules under `src/speakloop/`, each with its own `CLAUDE.md`
(Principles IV, XI). Dependency edges below are from an import scan (`rg "from speakloop\."`),
not prose (FR-007). Leaves: `config`, `content`, `trends`. Orchestrators: `cli` → 9 modules,
`sessions` → 6.

| Module | Responsibility | Depends on (internal) |
|--------|----------------|-----------------------|
| [`config/`](src/speakloop/config/CLAUDE.md) | Filesystem paths, Q&A-file resolution | — (leaf) |
| [`content/`](src/speakloop/content/CLAUDE.md) | Q&A YAML loader + schema (default `content/questions.yaml`) | — (leaf) |
| [`installer/`](src/speakloop/installer/CLAUDE.md) | Model manifest, consent, resumable download, validation | config |
| [`tts/`](src/speakloop/tts/CLAUDE.md) | TTS wrapper (**owns `kokoro_mlx`**) + clip cache | config, installer |
| [`audio/`](src/speakloop/audio/CLAUDE.md) | Playback, recording, device probing | sessions |
| [`asr/`](src/speakloop/asr/CLAUDE.md) | ASR wrapper (**owns `mlx_whisper`, `silero_vad`, `parakeet_mlx`**) + biasing | installer |
| [`llm/`](src/speakloop/llm/CLAUDE.md) | LLM wrapper (**owns `mlx_lm`** — Qwen3-14B 4-bit) | installer |
| [`metrics/`](src/speakloop/metrics/CLAUDE.md) | Per-attempt fluency metrics | asr |
| [`feedback/`](src/speakloop/feedback/CLAUDE.md) | Frontmatter, atomic writer, report builder, grammar analyzer | asr, config, llm |
| [`debrief/`](src/speakloop/debrief/CLAUDE.md) | Post-session interactive debrief (render + audio + menu) | feedback, tts |
| [`sessions/`](src/speakloop/sessions/CLAUDE.md) | 4/3/2 coordinator, timer, abort handling | asr, audio, config, content, feedback, metrics |
| [`trends/`](src/speakloop/trends/CLAUDE.md) | Cross-session dashboard + per-pattern series | — (leaf) |
| [`triage/`](src/speakloop/triage/CLAUDE.md) | [010] Hallucination filter (pre-grammar) + mishearing + artifact consistency | asr, config, feedback, llm |
| [`coverage/`](src/speakloop/coverage/CLAUDE.md) | [010] Key points (hash-versioned) + coverage scoring + content errors | asr, feedback, llm |
| [`srs/`](src/speakloop/srs/CLAUDE.md) | [010] Answer grade + interval ladder/mastery + due queue (pure logic) | store |
| [`warmup/`](src/speakloop/warmup/CLAUDE.md) | [010] Warm-up drill generation + deterministic pass/fail judge | config, feedback, llm |
| [`interviewer/`](src/speakloop/interviewer/CLAUDE.md) | [010] Unscripted follow-up generation (grounded in the learner's words) | asr, config, feedback, llm |
| [`store/`](src/speakloop/store/CLAUDE.md) | [010] Derived JSON store (SRS schedule + key-points + patterns), rebuildable | feedback (+srs) |
| [`cli/`](src/speakloop/cli/CLAUDE.md) | `typer` app: `practice`, `doctor`, `trends`, `today`, `rebuild`, `resume` | audio, config, content, feedback, installer, llm, sessions, trends, tts |

## Commands

Each verified by running it during this feature (see `specs/005-…/audit/command-matrix.md`).

```bash
uv run speakloop --help     # works with NO models downloaded (Principle VIII)
uv run speakloop doctor     # environment + model health check (exit 0 when healthy)
uv run pytest               # full suite — re-measure after each feature lands
uv run pytest -m live_asr   # real silero+torchaudio smoke — run when touching torchaudio
uv run pytest tests/integration/test_path_portability_audit.py   # no personal-path leakage
```

Linting uses `ruff` (config in `pyproject.toml [tool.ruff]`), but `ruff check .` currently
reports pre-existing findings on committed code, so it is **not** listed as a passing command
here (divergence D-7, deferred — fixing needs code edits).

## Conventions

Cross-verified against code and the constitution.

- **English-only** output everywhere (Principle I).
- **Engine imports are function-local** in their one wrapper file, so `--help` loads no models
  (Principle V + VIII).
- **Swappable engines**: replacing TTS/ASR/LLM touches exactly one wrapper file (Principle V).
- **`uv` only**; config is YAML; reports are Obsidian-compatible Markdown in `data/sessions/`
  named `YYYY-MM-DD-qXX.md` (Principle IX).
- **Report `schema_version` stays 1**; new frontmatter keys are additive only.
- **Conventional Commits** (`feat:`, `fix:`, `docs:`, …); every module ships its own `CLAUDE.md`.
- **Engine changes update the matching `doc/research_*.md`** (Principle X).

## Maintenance — how to keep this context layer true

Review is **feature-driven**: every new `specs/NNN-*` feature triggers this 7-item checklist
(≤ 2 minutes); plus any PR that changes a convention updates the relevant `CLAUDE.md` in the
same commit. No calendar cadence.

1. Re-read this file against the new feature's scope; update the SPECKIT block's active/prior
   lines and prune stale history (protects the ≤ 6000-token budget).
2. Run the documented commands (`--help`, `doctor`, `pytest`); remove any that now fail, add any new one.
3. For each module whose code changed (`git log --since=<last feature> -- src/speakloop/<mod>/`),
   re-check that module's `CLAUDE.md`.
4. Re-run the engine-import scan; confirm each engine package still resolves to exactly one wrapper (Principle V).
5. **Correct-twice-then-record**: if an agent is corrected on the same thing twice, add it here as a trap or never-do.
6. **PR-coupling**: any PR that changed a convention must have updated the relevant `CLAUDE.md` in the same commit — verify before merge.
7. Re-measure the launch footprint; if over 6000 tokens, push detail into a module file or a `paths`-scoped rule.

## Traps (evidence-cited)

1. **Don't bump `torchaudio` past `<2.9`** without `uv run pytest -m live_asr`: ≥2.11 moves
   decoding to unbundled `torchcodec`, crashing the first live VAD call (`pyproject.toml:29`,
   `asr/CLAUDE.md`, commit `21dfb86`).
2. **Keep engine imports function-local** — a module-level engine import would break `--help`.
   `tests/integration/test_help_without_models.py::test_importing_cli_loads_no_engine_packages`
   asserts importing the CLI loads none of `mlx_whisper`, `silero_vad`, `parakeet_mlx`, `mlx_lm`;
   `kokoro_mlx` is not yet covered by that guard (finding D-3).
3. **Research and manifest agree** on Qwen3-14B-4bit (May 2026). The prior
   Qwen3.5-9B-VLM divergence is **closed**; the historical context (Qwen3.5-9B-VLM →
   Qwen3-8B-4bit → Qwen3-14B-6bit → Qwen3-14B-4bit) lives in `doc/research_llm.md`.
   Thinking mode is ON; the wrapper strips the leading `<think>...</think>` block.
4. **No personal absolute paths** (`/Users/...`) in any committed file — the path-portability
   audit fails CI otherwise (`tests/integration/test_path_portability_audit.py`, `specs/004-…`).
5. **Q&A precedence is `--qa-file → ~/.speakloop/qa.yaml → repo default`, no auto-copy** — the
   home file is opt-in, not created for you (`config/paths.py:103` `resolve_qa_file`, `specs/004-…`).
6. **Never bump report `schema_version`** — add frontmatter keys additively only
   (`feedback/frontmatter.py:20,40,91`, specs 002/003).
7. **Grammar uses a free-form prompt (no catalog).** `error_type` strings come straight
   from the model and become `GrammarPattern.label`. The Persian-L1 catalog was retired
   in May 2026; `feedback/catalog.py` and `persian_l1_catalog.yaml` no longer exist. JSON
   recovery is `json-repair`, not hand-rolled regex — don't reintroduce the old repair
   regexes. The Qwen generation config (sampler top_p 0.8 / top_k 20 / min_p 0;
   `repetition_penalty` 1.05 / context 40; defensive `<|im_end|>` stop;
   `enable_thinking=True`; the `retry=True` bump to 1.15 / −0.1) lives **only** in
   `llm/qwen_engine.py`; the analyzer passes intent (`retry`) and `temperature=0.3`,
   never other engine config (`feedback/grammar_analyzer.py`). **4-bit at the 14B size
   is the current ship** (`mlx-community/Qwen3-14B-4bit`); 6-bit at 14B exceeded the
   M3 Pro 18 GB resident-memory budget alongside resident Whisper and was re-quantised
   down to 4-bit (CHANGELOG 2026-05-25). 8-bit stays out of scope.

## Never do

- Add a network call after model download (Principle II) — no telemetry, no auto-update.
- Import an engine package (`mlx_whisper`/`silero_vad`/`parakeet_mlx`/`mlx_lm`/`kokoro_mlx`)
  at module top level, or from more than one file (Principle V; breaks `--help`).
- Edit `.specify/memory/constitution.md` from a normal feature (governance amendment only).
- Ship non-English user-facing strings (Principle I).
- Introduce a GUI, a non-YAML user config, or a `pip install` workflow (constitution constraints).

## Pointers

- Per-module guidance: each `src/speakloop/<module>/CLAUDE.md` (loaded on-demand).
- Specs: `specs/001`–`specs/006` (plan.md · spec.md per feature).
- Engine research: `doc/research_tts.md`, `doc/research_asr.md`, `doc/research_llm.md`,
  `doc/research_methodology.md`; context-engineering reference: `doc/research_context_engineering.md`.
- Governance: `.specify/memory/constitution.md` (v1.0.0) — wins on any conflict.
