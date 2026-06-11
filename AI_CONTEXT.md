---
project: speakloop
purpose_one_line: Fully local, offline English speaking-practice CLI for non-native software engineers prepping for technical interviews.
primary_language: Python 3.12
runtime: CLI (typer + rich), three local MLX AI models (TTS / ASR / LLM)
platform: macOS on Apple Silicon (M-series)
status: v1 (version 0.1.0)
license: MIT
last_updated: 2026-05-25
version: 4
generated_by: claude-code
---

# AI_CONTEXT — speakloop

> Briefing for an LLM about to brainstorm improvements to this repo with the user.
> Density over prose. Every architectural claim points at a real path. This file
> describes the architecture **as it is today**, not as it should be — improvement
> ideas belong to the conversation this file enables, not to the file itself.

## Identity

speakloop is a command-line tool that helps non-native-English software engineers
practice **speaking** answers to technical-interview questions, fully offline, on
their own Apple-Silicon Mac. The user listens to a natively-spoken question and an
ideal answer (TTS), then records their own answer three times under shrinking time
budgets — the **4/3/2 method** (4 min, then 3, then 2). speakloop transcribes each
attempt (ASR), computes fluency metrics, runs an LLM grammar analysis tuned for
Persian-L1 transfer errors, and writes an Obsidian-compatible Markdown report whose
headline is the single highest-impact thing to fix next. The primary user is Persian
L1, but the design is L1-agnostic (`.specify/memory/constitution.md`, "User Context").

After the one-time model download, speakloop makes **zero network calls** — no
telemetry, no uploads; voice and reports never leave the device. It targets a
terminal-comfortable engineer who will read source to debug, not a casual consumer
(README.md:23–38). The deliberate rejections (GUI, cloud, other platforms,
localization) are enumerated in [Non-Goals](#non-goals); the governing principles
behind every claim in this section are the table in
[Invariants and Constraints](#invariants-and-constraints) (Principles I–XII).

The repo is also a deliberate exercise in **AI-collaborator-friendly structure**: 13
single-responsibility modules, each shipping its own `CLAUDE.md` contract so an agent
can modify one module without loading the rest (see Invariants → Principles IV, XI).

## Non-Goals

What speakloop deliberately is **not** — each rejection is a decision on record, not an
unbuilt feature. Brainstorming should treat these as load-bearing constraints, not gaps.

| Rejected option | Why it was rejected | Source |
|-----------------|---------------------|--------|
| A GUI (Tkinter / Qt / Electron / web UI) | CLI-only in v1; the target user lives in a terminal and the constraint is constitutional. | `constitution.md` "Non-Negotiable Constraints" (UI surface); README.md:30 |
| A cloud account / hosted backend | Privacy-by-design; voice and reports never leave the device. | README.md:30; `constitution.md` Principle III |
| Telemetry / analytics / error-reporting SaaS / remote config | Offline-first; zero network calls after model download. | `constitution.md` "Non-Negotiable Constraints" (External services); Principle II |
| Intel Macs, Linux, Windows support | Apple-Silicon-primary; other platforms are "best-effort, out of scope until v2." | README.md:37; `constitution.md` Principle VII (lines 138–139) |
| Localization / non-English UI | English-only by principle; no localization layer ships. | `constitution.md` Principle I (line 73); README.md (English-only) |
| A `pip install` workflow | `uv` is the only package manager; no pip-driven docs or scripts. | `constitution.md` "Non-Negotiable Constraints" (Package manager) |
| TOML / JSON / `.env` user config | User config is YAML, full stop. | `constitution.md` "Non-Negotiable Constraints" (User configuration) |
| External services beyond the HuggingFace download | The one allowed network dependency is the initial model fetch. | `constitution.md` "Non-Negotiable Constraints" (External services) |
| Phoneme-level pronunciation scoring | Out of scope for v1; speakloop scores fluency + grammar, not pronunciation. | README.md:193–194 |
| A "polished consumer app" experience | Deliberately a source-readable engineer's tool with honest edges. | README.md:30; `constitution.md` "User Context" (lines 263–266) |

## Quick Facts

| Fact | Value | Source |
|------|-------|--------|
| Language | Python, pinned `>=3.12,<3.13` (3.12 only) | `pyproject.toml:7` |
| Package manager | `uv` only — no `pip` workflows | `constitution.md` "Non-Negotiable Constraints"; CLAUDE.md |
| Build backend | `hatchling`; wheel packages `src/speakloop` | `pyproject.toml:35–40` |
| Platform | macOS / Apple Silicon (M-series); Metal + MLX | README.md:35; `constitution.md` Principle VII |
| UI surface | CLI only, rendered with `rich`; no GUI | `constitution.md` "Non-Negotiable Constraints" |
| Install | `git clone … && cd speakloop && uv sync` | README.md:44–48 |
| Entry-point command | `uv run speakloop` → `speakloop.cli.main:app` | `pyproject.toml:32–33` |
| Help without models | `uv run speakloop --help` (≤ 2 s, no model load) | `cli/main.py:1–7`; `constitution.md` Principle VIII |
| Health check | `uv run speakloop doctor` (exit 0 when healthy) | `cli/doctor.py` |
| Version | `0.1.0` | `src/speakloop/__init__.py:1` |
| Reports land at | `<cwd>/data/sessions/YYYY-MM-DD-qXX.md` (gitignored; `.gitkeep` only) | `config/paths.py:59–65`; `constitution.md` Principle IX |
| Models land at | `~/.speakloop/models/<repo-slug>/` | `config/paths.py:50–56`; `installer/manifest.py:26–28` |
| TTS clip cache | `~/.speakloop/cache/tts/<sha256>.wav` | `config/paths.py:127–131`; `tts/cache.py` |
| Default questions | in-repo `content/questions.yaml` (4 questions) | `config/paths.py:94–100`; `content/questions.yaml` |
| Report schema | YAML frontmatter, `schema_version` fixed at **1** (additive-only) | `feedback/frontmatter.py:11` |
| Test suite | 67 `test_*.py` files (unit/contract/integration); CLAUDE.md records 306 passed / 3 skipped at audited HEAD (not re-run here) | `tests/`; CLAUDE.md "Commands" |

### Key runtime dependencies (`pyproject.toml:9–30`)

| Dependency | Pin | Role |
|------------|-----|------|
| `typer` | `>=0.12` | CLI framework |
| `rich` | `>=13.7` | terminal rendering / progress |
| `pyyaml` | `>=6.0` | YAML user config + report frontmatter parse |
| `python-frontmatter` | `>=1.1` | read report YAML in `trends` |
| `numpy` | `>=1.26` | audio buffers |
| `scipy` | `>=1.13` | device-rate-mismatch resample fallback (`audio/playback.py:66`) |
| `sounddevice` | `>=0.4` | record + playback |
| `soundfile` | `>=0.12` | WAV I/O |
| `huggingface_hub` | `>=0.24` | resumable model download |
| `kokoro-mlx` | `>=0.1.2` | **TTS engine** (Kokoro-82M) |
| `mlx-whisper` | `>=0.4.2` | **default ASR engine** (Whisper-large-v3-turbo) |
| `parakeet-mlx` | `>=0.5.1` | **fallback ASR engine** (Parakeet-TDT) |
| `silero-vad` | `>=5.1` | voice-activity detection (Whisper path) |
| `mlx-lm` | `>=0.31.3` | **LLM engine** (Qwen3-14B 4-bit; thinking ON, stripped at wrapper) |
| `onnxruntime` | `>=1.20` | **required direct dep** (no import in `src/`): `asr/vad.py:97` loads silero with `onnx=True`, and `silero-vad` ≥6 declares `onnxruntime` only under its onnx extras (D-1 revised) |
| `torchaudio` | `<2.9` | capped: ≥2.11 moves decode to unbundled `torchcodec` and crashes live VAD (see Invariants/Trap) |

Dev deps: `pytest>=8.0`, `pytest-mock>=3.12`, `ruff>=0.6` (`pyproject.toml:51–56`).

Each engine package is imported function-local inside exactly one wrapper file
(Principle V); the owning files are annotated in bold in the [Module Map](#module-map).

### Models downloaded per phase (`installer/manifest.py`)

| Model | HF repo | Approx size | Phase |
|-------|---------|-------------|-------|
| Kokoro-82M | `mlx-community/Kokoro-82M-bf16` | ~170 MB | A |
| Whisper-large-v3-turbo (default ASR) | `mlx-community/whisper-large-v3-turbo` | ~1.50 GiB | B |
| Parakeet-TDT-0.6b-v3 (fallback ASR) | `mlx-community/parakeet-tdt-0.6b-v3` | ~2.34 GB | B |
| Qwen3-14B-4bit (LLM) | `mlx-community/Qwen3-14B-4bit` | ~8 GB | C |

### Top-level repository layout

| Path | Contents |
|------|----------|
| `src/speakloop/` | The 13 source modules (each with its own `CLAUDE.md`). |
| `tests/` | 67 test files across `unit/` (per-module), `contract/` (protocol shapes), `integration/` (end-to-end with stubs), plus `fixtures/`. |
| `content/questions.yaml` | The in-repo default Q&A set (4 questions, Android-domain). |
| `data/sessions/` | Report output target; gitignored except a `.gitkeep` (Principle III — reports are local-only). |
| `doc/` | The 6 research docs (`research_{tts,asr,asr_l2_accent,llm,methodology,context_engineering}.md`). |
| `specs/` | Spec Kit feature folders `001-…`–`005-…` (each: `spec.md`, `plan.md`, `tasks.md`, research, contracts). |
| `.specify/` | Spec Kit machinery: `memory/constitution.md`, templates, scripts, workflows. |
| `CLAUDE.md` | Root agent guidance + architecture map (the human-and-agent companion to this file). |
| `pyproject.toml`, `uv.lock` | Manifest + locked resolution (exact versions). |
| `LICENSE`, `README.md` | MIT license; user-facing docs. |
| `interview/` | Empty, gitignored local scratch dir (see Open Questions). |

## Performance Profile

speakloop is interactive and model-heavy, so most latency is dominated by on-device
model loads and the user's own speaking time. The numbers below are split by how much
confidence the source actually supports.

### Documented / stated

Every concrete timing or size already promised in code or docs, with its cite.

| Quantity | Value | Source |
|----------|-------|--------|
| `speakloop --help` / `--version` | ≤ 2 s, no model load | `cli/main.py:1–7` (FR-018, SC-006) |
| Start → first saved report | "a few minutes once the models are downloaded" (qualitative) | README.md:71 |
| Per-attempt time budgets (4/3/2) | 240 s / 180 s / 120 s | `sessions/timer.py:18` (`BUDGETS = (240, 180, 120)`) |
| ASR engine cold load | probed **eagerly** via `ensure_loaded()` before attempt 1, so it sits outside the timed loop (warm model per attempt) | `cli/practice.py:300–305`, `asr/selection.py` |
| REPLAY → "press space to begin attempt 1" | < 3 s (resident engine reused, no reload) | `cli/practice.py:294–296` (SC-004) |
| Kokoro-82M download | ~170 MB (Phase A) | `installer/manifest.py` |
| Whisper-large-v3-turbo download | ~1.50 GiB (Phase B) | `installer/manifest.py` |
| Parakeet-TDT-0.6b-v3 download | ~2.34 GB (Phase B, fallback) | `installer/manifest.py` |
| Qwen3-14B-4bit download | ~8 GB (Phase C) | `installer/manifest.py` |

### Inferable bounds

Deducible from static reading alone, without running anything.

- **Per-attempt wall time ≥ the attempt's time budget** unless the user ends early with
  Enter (`early_exit_event`) — the timer blocks up to `budget_seconds`
  (`sessions/timer.py:48–60`).
- **Minimum talk time for a full session ≈ 540 s** (240 + 180 + 120) if no early exit,
  before any TTS playback, ASR transcription, or Phase-C analysis is added.
- **Total session time ≥ Σ(attempt budgets) + listen-phase playback + 3× ASR transcribe
  + Phase-C analysis** — each is strictly additive in the coordinator's serial state
  machine (`sessions/coordinator.py`).
- **Report write is a single atomic `os.replace`** (temp file then rename), so the write
  itself is negligible and never leaves a half-written report (`feedback/markdown_writer.py`,
  `write_atomic`).
- **`--help`/`doctor` never pay model-load cost** because engine imports are function-local
  (guarded; see Invariants).

### Unknown without instrumentation

These cannot be derived statically — they need a run on real hardware. Each is mirrored
into [Open Questions](#open-questions) with the measurement that would resolve it.

- Cold-start load latency of **Whisper vs Parakeet vs Qwen** on a given M-series chip.
- **Phase-C grammar-analysis duration per attempt** (Qwen `generate` wall time).
- **End-to-end median session duration** including playback, ASR, and debrief.

## End-to-End Flow

Primary journey: **`uv run speakloop practice`** (a full 4/3/2 session). Listen-only,
`doctor`, and `trends` are noted after. Each step names the owning module/file.

1. **Dispatch.** `speakloop.cli.main:app` (typer) parses args. The root callback wires
   `--qa-file` / `--models-dir` overrides into `config.paths`. The `practice` command
   defers all engine-touching imports to function scope so `--help` stays model-free.
   → `cli/main.py:33–86`
2. **Resolve the question file.** `cli/practice.py:_resolve_qa_file` calls
   `config.paths.resolve_qa_file()` (precedence chain documented once in
   [Invariants](#invariants-and-constraints); no file is auto-created, exit 1 with
   guidance if none resolves). → `cli/practice.py:18–37`, `config/paths.py:103–124`
3. **Load + validate Q&A.** `content.load(path)` parses YAML and validates each entry
   against `content.schema.Question` (kebab-case id, required `question`/`ideal_answer`,
   optional `tags`/`difficulty`/`voice_override`). → `content/loader.py`,
   `content/schema.py`
4. **Pick a question.** `--question <id>` jumps directly; otherwise a numbered picker.
   → `cli/practice.py:40–60`, `:246–256`
5. **Choose phase + ensure models.** `--listen-only` → Phase A (TTS only); else Phase B
   (TTS + ASR). `installer.ensure_models(phase)` computes what's missing, prompts for
   consent (decline-by-default, size disclosure), and resumably downloads via
   `huggingface_hub.snapshot_download(resume_download=True)`, then re-validates.
   → `cli/practice.py:261–270`, `installer/__init__.py`, `installer/consent.py`,
   `installer/downloader.py`, `installer/validator.py`, `installer/manifest.py`
6. **Build the TTS engine.** `tts.kokoro_engine.KokoroEngine` (lazy `kokoro_mlx` load);
   playback via `audio.playback.play`. → `cli/practice.py:272–277`
7. **Listen loop.** Synthesize question + ideal answer (cached by `sha256(voice|text)`),
   play them, and accept replay keys: `r` replay question, `R` replay ideal answer,
   `space` advance to attempts, `q`/Enter quit. → `cli/practice.py:178–223`
   - **`--listen-only` returns here** — no recording, no debrief (Phase A complete).
8. **Microphone pre-check.** If `audio.devices.default_input()` is `None`, exit 1 and
   point at `doctor`. → `cli/practice.py:285–287`
9. **Resolve the ASR engine once.** `asr.build_engine(choice)` constructs the default
   Whisper (or `--asr-engine parakeet`), **eagerly probes the load** (`ensure_loaded`)
   so a missing model/OOM surfaces before attempt 1, and **falls back to Parakeet** with
   one English reason on load failure. The resident engine is reused across attempts,
   sessions, and replays (no reload). → `cli/practice.py:305–313`, `asr/selection.py`
10. **Build the grammar analyzer (Phase C, optional).** If `Qwen3-14B-4bit` validates as
    present, wrap `feedback.grammar_analyzer.analyze` over a lazily-loaded `QwenEngine`;
    otherwise `None` → the session degrades to Phase B (fluency-only).
    → `cli/practice.py:358–373`
11. **Run the session (the 4/3/2 state machine).** `sessions.coordinator.run_session`:
    state `listening → attempt_1 → attempt_2 → attempt_3 → analyzing → reporting → done`.
    A SIGINT handler (`sessions.abort`) cleans `*.tmp` + scratch audio and exits 130 with
    no report written. → `sessions/coordinator.py:234–363`, `sessions/abort.py`
    - **Per attempt** (`coordinator._do_attempt`, `:123–192`): show a `rich` countdown
      (`sessions.timer`), record to `attempt-N.wav` via `audio.recorder.record` (Enter
      ends early via a background tty reader thread), then `asr_engine.transcribe(wav,
      context=…)`. Time budgets come from `timer.time_budget_for(ordinal)`.
    - **Domain biasing** (`asr.domain_context.build_context`): mines question + ideal
      answer + tags + a seed lexicon + a Persian-accent declaration into an
      `initial_prompt`, hashed to `initial_prompt_sha256`. Injected into every
      transcription; engines that can't use it ignore it. The Whisper path additionally
      runs Silero VAD pre-segmentation (`asr/vad.py`); Parakeet does not (RNN-T/TDT does
      not hallucinate on silence).
12. **Compute fluency metrics.** `metrics.compute_all(transcript)` → words_total,
    speech_rate_wpm, filler count + density, pause count + mean_pause_ms,
    self_corrections. Deterministic, transcript-only, no LLM. → `coordinator._build_attempts:195–218`,
    `metrics/__init__.py`
13. **Grammar analysis (Phase C).** `feedback.grammar_analyzer.analyze(transcripts, llm)`:
    **free-form** — the LLM returns its own `error_type` strings which become
    `GrammarPattern.label`. Coherence-filtered (drops ASR-garble),
    verbatim-substring-guaranteed quotes, no-op fixes suppressed, sorted by
    `(-occurrence_count, label)` with `impact_rank` 1..N. On any exception the session
    records `phase_c_error` and falls back to Phase B.
    → `coordinator.py:314–328`, `feedback/grammar_analyzer.py`, `feedback/coherence.py`
14. **Compose narrative + top priority.** `feedback.narrative.build_narrative` and
    `select_top_priority` produce deterministic, persisted prose (cross-attempt narrative
    + the single most-impactful fix). Computed for every phase. → `coordinator.py:355–356`
15. **Assemble + write the report atomically.** Build a `feedback.frontmatter.Session`
    (incl. additive `asr:` provenance + optional `phase_c_error`), render with
    `feedback.report_builder.build`, and write via
    `feedback.markdown_writer.write_atomic` (temp file + `os.replace`) to a
    disambiguated `YYYY-MM-DD-qXX.md`. Returns `(report_path, session)`.
    → `coordinator.py:343–363`, `feedback/markdown_writer.py`, `feedback/frontmatter.py`
16. **Interactive debrief.** `debrief.run(session, …)` renders the finished session
    (`rich.Live` banner/cards/transcripts), reads only the educational parts aloud via
    the injected `tts_engine` + `play_fn` (`--no-audio` skips audio), and returns a
    `DebriefChoice`. → `cli/practice.py:336–343`, `debrief/debrief.py`, `debrief/renderer.py`,
    `debrief/audio_player.py`, `debrief/menu.py`
17. **Loop on the menu choice.** `REPLAY` → same question, fresh 4/3/2, **skip the listen
    phase**, reuse resident engines (< 3 s to attempt 1). `NEW` → re-open the picker.
    `QUIT` → return to the shell. → `cli/practice.py:345–355`

**Other commands:**
- `doctor` (`cli/doctor.py`): checks Python 3.12, each Phase-C model's presence/size,
  default output + input audio devices, and the sessions dir; `--json` for scripting;
  non-zero exit on failure.
- `trends` (`cli/trends.py` → `trends/reader.py` → `trends/aggregator.py` →
  `trends/renderer.py`): reads past reports' frontmatter and renders an aggregate
  fluency/grammar dashboard. `--since YYYY-MM-DD`, `--top-patterns N`.

## Module Map

13 single-responsibility packages under `src/speakloop/`, each shipping its own
`CLAUDE.md` (Principle IV). Internal edges below are from an import scan
(`rg "from speakloop\."`). Leaves (nothing internal depends on them): `config`,
`content`, `trends`. "Depends on" = internal imports; "Consumers" = who imports it.

| Path | Responsibility (one sentence) | Key files | Public contract | Depends on | Consumers |
|------|-------------------------------|-----------|-----------------|------------|-----------|
| `src/speakloop/config/` | Single source of truth for filesystem paths and Q&A-file resolution (leaf, no I/O beyond `mkdir -p`). | `paths.py` | `models_dir()`, `sessions_dir()`, `default_qa_file()`, `qa_file_path()`, `resolve_qa_file()`, `tts_cache_dir()`, `set_*` overrides | — | `cli`, `feedback`, `installer`, `sessions`, `tts` |
| `src/speakloop/content/` | Loads + validates a Q&A YAML file; never chooses or creates one (leaf). | `loader.py`, `schema.py` | `load(path) -> QAFile`, `Question`, `QAFile`, `QALoadError`, `QASchemaError` | — | `cli`, `sessions` |
| `src/speakloop/installer/` | Model lifecycle: compute-missing → consent → resumable download → re-validate; owns the per-phase manifest. | `manifest.py`, `consent.py`, `downloader.py`, `validator.py` | `ensure_models(phase, …)`, `manifest.Model/Phase/models_for_phase`, `consent.prompt_for_consent`, `downloader.download_model`, `validator.validate`, `InstallDeclinedError`, `InstallFailedError` | `config` | `asr`, `cli`, `llm`, `tts` |
| `src/speakloop/tts/` | TTS wrapper (Kokoro-82M) behind a stable Protocol + content-addressed clip cache; **owns `kokoro_mlx`**. | `interface.py`, `kokoro_engine.py`, `cache.py` | `TTSEngine` Protocol (`synthesize(text, voice=None) -> Path`, `available_voices()`), `TTSEngineError` | `config`, `installer` | `cli`, `debrief` |
| `src/speakloop/audio/` | Local audio I/O — mic recording, clip playback, device probing (no model packages). | `playback.py`, `recorder.py`, `devices.py` | `playback.play(wav)`, `recorder.record(out, budget, early_exit_event) -> duration`, `devices.default_input/default_output/list_devices` | `sessions` (shared abort event) | `cli`, `sessions` |
| `src/speakloop/asr/` | Speech-to-text wrapper + per-session domain biasing + Silero VAD; default Whisper, Parakeet fallback; **owns `mlx_whisper`, `silero_vad`, `parakeet_mlx`**. | `interface.py`, `selection.py`, `whisper_mlx_engine.py`, `vad.py`, `parakeet_engine.py`, `domain_context.py`, `seed_lexicon.py` | `ASREngine` Protocol (`transcribe(wav, *, context=None)`, `ensure_loaded()`), `Transcript`, `WordTiming`, `TranscriptionContext`, `ASREngineError`, `build_engine(name=None) -> EngineSelection`, `domain_context.build_context(question)` | `installer` | `feedback`, `metrics`, `sessions` |
| `src/speakloop/llm/` | LLM wrapper (Qwen3-14B 4-bit, thinking ON) behind a stable Protocol for Phase-C grammar feedback; **owns `mlx_lm`**. | `interface.py`, `qwen_engine.py` | `LLMEngine` Protocol (`generate(system, user, max_tokens=2048, temperature=0.7, retry=False) -> str`), `LLMEngineError` | `installer` | `cli`, `feedback` |
| `src/speakloop/metrics/` | Deterministic per-attempt fluency metrics from a transcript only (no LLM). | `__init__.py`, `speech_rate.py`, `pauses.py`, `fillers.py`, `self_corrections.py` | `compute_all(transcript) -> dict`; per-metric `compute()` | `asr` (types only) | `sessions` |
| `src/speakloop/feedback/` | Session-report assembly (versioned frontmatter + Markdown body) plus the educational grammar/coherence analysis. | `frontmatter.py`, `markdown_writer.py`, `report_builder.py`, `grammar_analyzer.py`, `coherence.py`, `narrative.py` | `frontmatter.Session/dump/parse` (schema 1; additive-optional keys: `ideal_answer`, `asr`, `phase_c_error`, `cross_attempt_narrative`, `top_priority`), `markdown_writer.write_atomic/next_available_path`, `report_builder.build(session)`, `grammar_analyzer.analyze(transcripts, llm)` (free-form prompt — no catalog), `narrative.build_narrative/select_top_priority`, `coherence` filter | `asr`, `config`, `llm` | `cli`, `debrief`, `sessions` |
| `src/speakloop/debrief/` | Post-session interactive debrief: render + read-aloud + menu (renders the in-memory `Session`, never re-reads the file). | `debrief.py`, `view_model.py`, `renderer.py`, `audio_player.py`, `menu.py` | `run(session, *, sessions_dir, tts_engine, play_fn, no_audio=False) -> DebriefChoice`, `DebriefChoice` (`REPLAY`/`NEW`/`QUIT`) | `feedback`, `tts` | `cli` (function-local import) |
| `src/speakloop/sessions/` | Orchestrator for the 4/3/2 loop: state machine, per-attempt timer, clean SIGINT abort. | `coordinator.py`, `timer.py`, `abort.py` | `coordinator.run_session(question, …) -> SessionResult`, `timer.run/time_budget_for`, `abort.install_signal_handler/reset/cleanup_tmp_files`, `AbortedError` | `asr`, `audio`, `config`, `content`, `feedback`, `metrics` | `audio`, `cli` |
| `src/speakloop/trends/` | Cross-session progress dashboard (leaf; nothing in `src/` depends on it). | `reader.py`, `aggregator.py`, `renderer.py` | `reader.read_reports(dir, since=None)`, `aggregator.aggregate(reports, top_n) -> TrendsSummary`, `renderer.render(summary)` | — | `cli` |
| `src/speakloop/cli/` | `typer` app + top-level dispatch; the only module wiring every other module together. | `main.py`, `practice.py`, `doctor.py`, `trends.py` | `main.app` with commands `practice`, `doctor`, `trends` | `audio`, `config`, `content`, `feedback`, `installer`, `llm`, `sessions`, `tts`, `trends` (+ `debrief`, `asr` function-local) | — (console entry point) |

## Domain Glossary

| Term | Definition |
|------|------------|
| **4/3/2 method** | A fluency drill: deliver the same answer three times, in 4-, then 3-, then 2-minute budgets. Budgets in `sessions/timer.py`; see `doc/research_methodology.md`. |
| **Phase A / B / C** | Iterative shipping tiers (Principle XII). A = TTS listen-only; B = + ASR attempts + fluency metrics; C = + LLM grammar feedback + trends. Each phase is a complete working system. |
| **TTS / ASR / LLM** | Text-to-speech (Kokoro), automatic speech recognition (Whisper default / Parakeet fallback), large language model (Qwen3-14B at MLX 4-bit, thinking ON). Each behind a swappable Protocol. |
| **Engine wrapper** | The single file that imports a given engine package (function-local) and adapts it to the module's Protocol — e.g. `asr/whisper_mlx_engine.py`. |
| **`ASREngine` / `TTSEngine` / `LLMEngine` Protocols** | The stable interfaces (in each module's `interface.py`) every consumer depends on; swapping an engine means a new wrapper, not a changed Protocol. |
| **`EngineSelection`** | Frozen dataclass from `asr.build_engine`: the resident engine + `engine_name`, `model_id`, `fell_back`, `fallback_reason` (`asr/selection.py:26–34`). |
| **`fell_back`** | True when the requested ASR engine failed to load and Parakeet was substituted; recorded in report provenance so a fallback is debuggable. |
| **VAD** | Voice-activity detection (Silero). Drops silence before Whisper transcribes so pauses don't produce phantom tokens; Whisper path only (`asr/vad.py`). |
| **Domain biasing / `initial_prompt`** | A per-session prompt mined from the question + ideal answer + tags + seed lexicon + a Persian-accent declaration, fed to ASR to bias toward domain terms. Hashed to `initial_prompt_sha256` for provenance (`asr/domain_context.py`). |
| **Seed lexicon** | A curated base list of technical terms folded into the biasing prompt (`asr/seed_lexicon.py`). |
| **`TranscriptionContext`** | The additive, optional biasing payload passed into `transcribe` (`initial_prompt`, `initial_prompt_sha256`, `use_vad`) (`asr/interface.py:45–60`). |
| **Transcript / WordTiming** | Frozen ASR result: text + per-word start/end seconds + audio duration (`asr/interface.py:22–42`). |
| **Fluency metrics** | Deterministic transcript-only signals: speech_rate_wpm, filler count + density, pause count + mean_pause_ms (250 ms threshold), self_corrections (`metrics/`). |
| **Persian-L1 transfer-error catalog** | **Retired** May 2026. A curated catalog of grammar mistakes Persian speakers transfer into English, used through feature 006 to label and explain patterns. Replaced by free-form `error_type` strings from the LLM; the term no longer maps to any in-repo artifact. |
| **Grammar pattern** | A labeled, evidence-cited grammar issue with `occurrence_count`, `explanation` ("Because:"), evidence quote + `corrected` ("Better:"), `suggested_fix`, and `impact_rank` (`feedback/frontmatter.py:14–33`). |
| **`impact_rank`** | Deterministic 1-based ranking of grammar patterns by interview comprehensibility impact; 1 = highest. Drives render/read-aloud order. |
| **`top_priority`** | The single most important fix next session, chosen across grammar + fluency by a most-impactful-wins rule; rendered as the debrief banner (`feedback/narrative.select_top_priority`). |
| **Cross-attempt narrative** | Deterministic prose describing what improved across the 4/3/2 rounds; persisted in the report (`feedback/narrative.build_narrative`). |
| **Coherence / garble filter** | A deterministic filter that drops ASR-garble before grammar analysis so the LLM isn't "correcting" mis-transcriptions (`feedback/coherence.py`). |
| **`phase_c_error`** | Frontmatter field holding the LLM analyzer's exception message when Phase C failed and the session degraded to Phase B — diagnosable from the saved file alone. |
| **`schema_version`** | Stable report-frontmatter version, fixed at **1**; all later additions are additive optional keys (`feedback/frontmatter.py:11`). The Q&A file also carries its own `schema_version: 1` (`content/schema.py:56–58`) — a separate counter. |
| **`asr:` provenance block** | Top-level report key recording engine, model, `initial_prompt` + hash, VAD settings, and `fell_back` — emitted only when present (`feedback/frontmatter.py:35–52`). |
| **`Session` model** | The in-memory typed report (`feedback/frontmatter.py:74–96`) returned by `run_session` and rendered by both `report_builder` and `debrief`. |
| **`DebriefChoice`** | The post-session menu outcome: `REPLAY` / `NEW` / `QUIT` (`debrief/menu.py:23–28`). |
| **`resolve_qa_file` precedence** | Active-question-file resolution with no auto-copy; the full precedence chain is documented once in [Invariants](#invariants-and-constraints) (`config/paths.py:103–124`). |
| **Obsidian-compatible report** | A Markdown file with YAML frontmatter under `data/sessions/`, named `YYYY-MM-DD-qXX.md`, that renders/links cleanly as an Obsidian vault (Principle IX). |
| **Two-tier tty read** | The repo's reusable key-input pattern: raw single-byte `termios`/`cbreak` read (stdin, then `/dev/tty`), with a line-buffered `input()` fallback for piped/scripted use (`cli/practice.py:63–175`, `debrief/menu.py`). |
| **Constitution / Principle N** | `.specify/memory/constitution.md` — the 12 governing principles (I–XII) that win on any conflict. |
| **Spec Kit (`.specify/`, `specs/`)** | The feature-driven workflow: each feature is a numbered `specs/NNN-*/` folder (spec.md · plan.md · tasks.md · research). |
| **`scratch_dir` / `.tmp-audio`** | Per-session temp directory (`data/sessions/.tmp-audio`) holding `attempt-N.wav` files; removed on completion and on abort (`sessions/coordinator.py:259, 304–308`). |
| **`early_exit_event`** | A `threading.Event` letting the user end an attempt before its time budget by pressing Enter; a background tty reader thread sets it (`sessions/coordinator.py:53–120`). |
| **`next_available_path`** | Disambiguates report filenames so a second session for the same question/day doesn't overwrite the first (`feedback/markdown_writer.py`; `tests/integration/test_phase_b_filename_disambiguation.py`). |
| **`SessionResult`** | `run_session`'s return — `(report_path, session)` — so the debrief renders typed data without re-parsing the Markdown (`sessions/coordinator.py:41–52`). |

## Invariants and Constraints

Sourced from `.specify/memory/constitution.md` (v1.0.0, wins on conflict), the root
`CLAUDE.md`, and `README.md`.

### Constitutional principles (I–XII)

| # | Principle | Practical rule |
|---|-----------|----------------|
| I | English-Only UI | Every user-facing string is English; no localization layer. |
| II | Offline-First | After model download, **zero** network calls — no telemetry, analytics, phone-home, auto-update, or remote flags. |
| III | Privacy by Design | Audio, transcripts, reports stay on the user's machine; no path uploads anything. |
| IV | Modular by Design (NON-NEGOTIABLE) | One responsibility per module; modules talk through documented interfaces; **every module ships a `CLAUDE.md`** or it must not merge. |
| V | Swappable Engines | TTS/ASR/LLM sit behind stable Protocols; swapping one engine changes exactly one wrapper file; no engine-specific import leaks across module boundaries. |
| VI | Resumable Model Downloads | Downloads survive interruption; never re-download what's complete (`resume_download=True`). |
| VII | Apple Silicon Primary | M-series Macs are the design target; Intel/Linux/Windows out of scope for v1. |
| VIII | Easy Install for Everyone | `git clone` + `uv run speakloop` reaches a working setup; `--help` works with **no** models; consent + size disclosure before any download. |
| IX | Obsidian-Compatible Reports | Markdown + YAML frontmatter under `data/sessions/`, `YYYY-MM-DD-qXX.md`, stable versioned schema. |
| X | Research is Part of the Repo | Engine/methodology rationale lives in `doc/research_*.md`; changing an engine without updating the matching research doc is a violation. |
| XI | AI-Collaborator Friendly | Structure exists so an agent edits one module without loading the rest; widening required context is a regression. |
| XII | Iterative Delivery | MVP (TTS-only) is usable before ASR/LLM; later phases are strict supersets that don't break earlier ones. |

### Non-negotiable constraints

- **Python** 3.11+ (3.12 recommended; repo pins 3.12 only).
- **Package manager** `uv` only — no `pip install` workflows in docs or scripts.
- **Model storage** under `~/.speakloop/models/` (override `--models-dir` /
  `SPEAKLOOP_MODELS_DIR` / `SPEAKLOOP_HOME`).
- **User config is YAML** — no TOML/JSON/`.env` for user-facing config.
- **CLI only** in v1, rendered with `rich`; no GUI framework ships.
- **External services**: none beyond the initial HuggingFace download.
- **License** MIT; **repository public** on GitHub.

### Code-level invariants the project will not break (with traps)

| Invariant | Why / trap | Evidence |
|-----------|------------|----------|
| Engine imports are **function-local in one wrapper file** | A module-top-level engine import breaks `--help` (Principle VIII). | `tests/integration/test_help_without_models.py`, `tests/unit/asr/test_engine_import_isolation.py`; CLAUDE.md Trap 2 |
| `kokoro_mlx` is **not yet** covered by the import-isolation guard | Finding D-3 — coverage gap, not a passing guard. | CLAUDE.md Trap 2 |
| **Don't bump `torchaudio` past `<2.9`** without `uv run pytest -m live_asr` | ≥2.11 moves decoding to unbundled `torchcodec`, crashing the first live VAD call. | `pyproject.toml:29`, `asr/CLAUDE.md`, commit `21dfb86`; CLAUDE.md Trap 1 |
| **Report `schema_version` stays 1** | New keys are additive + optional; a bump breaks trends/back-compat. | `feedback/frontmatter.py:11`; CLAUDE.md Trap 6 |
| LLM and research **agree** on Qwen3-14B at MLX 4-bit (closed divergence) | The prior Qwen3.5-9B-VLM divergence is retired; manifest and research both target Qwen3-14B-4bit (re-quantised down from 6-bit in May 2026 to fit the M3 Pro 18 GB resident-RAM budget alongside resident Whisper). | `installer/manifest.py`; `llm/CLAUDE.md`; `doc/research_llm.md` (Update — 2026-05-25) |
| Qwen3-14B **thinking mode is enabled**; leading `<think>...</think>` stripped at the wrapper boundary | The Qwen3-14B chat template emits a reasoning prelude; the wrapper's leading-only regex strips it so callers see clean JSON. A truncated thinking pass triggers the analyzer's bounded regenerate path. | `llm/qwen_engine.py:_strip_artefacts`; `llm/CLAUDE.md`; `doc/research_llm.md` (May 2026) |
| **No personal absolute paths** (`/Users/...`) in committed files | Path-portability audit fails CI otherwise. | `tests/integration/test_path_portability_audit.py`; CLAUDE.md Trap 4 |
| Q&A precedence is `--qa-file → ~/.speakloop/qa.yaml → repo default`, **no auto-copy** | The home file is opt-in, never created for you. | `config/paths.py:103–124`; CLAUDE.md Trap 5 |
| `metrics` must **never import `speakloop.llm`** or a model package | Metrics are deterministic + offline. | `metrics/self_corrections.py:3`; `metrics/CLAUDE.md` |
| Debrief **never reads transcripts/raw metrics aloud**, never re-reads the report file, and must never hang | FR-017; a TTS/playback failure still reaches the menu. | `debrief/CLAUDE.md` |
| `onnxruntime` declared but **never imported in `src/`** | Load-bearing nonetheless: `asr/vad.py:97` calls `load_silero_vad(onnx=True)`, and `silero-vad` ≥6 declares `onnxruntime` only under its onnx extras — don't remove it (D-1 revised). | `pyproject.toml:37`; `asr/CLAUDE.md` |
| `.specify/memory/constitution.md` is **read-only** to normal features | Edits require the governance amendment process. | `constitution.md` "Governance"; CLAUDE.md Never-do |

> **Known divergence, deferred (D-7):** `ruff check .` reports pre-existing findings on
> committed code, so it is **not** a listed passing command (fixing needs code edits).
> See CLAUDE.md "Commands".

## Extension Points

Where new capability plugs in safely, with the interface/seam to implement against.

| To add… | Do this | Seam / file |
|---------|---------|-------------|
| A new **ASR engine** | Implement the `ASREngine` Protocol in a new `asr/<name>_engine.py`, keep its package import function-local, add a manifest `Model`, and wire it into `selection.build_engine`. Touch no other module. | `asr/interface.py` (`ASREngine`), `asr/selection.py`, `installer/manifest.py` |
| A new **TTS engine** | Implement `TTSEngine` (`synthesize`, `available_voices`) in a new `tts/<name>_engine.py`; keep the package import function-local; add at most a manifest entry. Protocol shape must not change. | `tts/interface.py`, `installer/manifest.py` |
| A new **LLM** | Implement `LLMEngine.generate` in a new `llm/<name>_engine.py`; point the model id at a manifest entry; keep the import function-local. | `llm/interface.py`, `installer/manifest.py` |
| A new **fluency metric** | Add a `compute()` in a new `metrics/<name>.py` and call it from `compute_all`; thresholds live in that one file. | `metrics/__init__.py` |
| A new **frontmatter field** | Add it as an **optional** field on the relevant dataclass; emit only when present; **never bump `schema_version`**. | `feedback/frontmatter.py` |
| A new **grammar pattern label** | No catalog: labels are free-form `error_type` strings the LLM emits, which become `GrammarPattern.label` verbatim. Tune behavior by editing the free-form prompt in `grammar_analyzer.py` (keep the verbatim-substring guarantee for evidence quotes; engine config — sampler / rep-penalty / stop — lives in `llm/qwen_engine.py`, not here). | `feedback/grammar_analyzer.py` (the free-form prompt and `_verify_and_enrich`) |
| A new **question field** | Add it (optional, back-compatible) to `schema.Question` and validate in `loader.load`; match the content-schema contract. | `content/schema.py`, `content/loader.py`, `specs/001-v1-product-spec/contracts/content-schema.yaml` |
| A new **CLI command** | Add an `@app.command(...)` in `main.py` delegating to a thin module here; keep engine-touching imports function-local. | `cli/main.py` |
| A new **`practice` flag** | Edit `cli/practice.py`; keep engine resolution injected once before the loop. | `cli/practice.py` |
| A new **trend metric** | Extend `aggregator.aggregate` + `renderer.render`; respect `schema_version` 1 in `reader`. | `trends/aggregator.py`, `trends/renderer.py`, `trends/reader.py` |
| A new **path / constant** | Add a function in `config/paths.py`; never hard-code a path elsewhere. | `config/paths.py` |
| A new **model build / swap** | Edit the `manifest.py` entry (id, repo, expected size) only. | `installer/manifest.py` |

Engine selections must update the matching `doc/research_*.md` (Principle X). Every new
module must ship its own `CLAUDE.md` (Principle IV).

## Friction & Brittleness Map

The maintainer-internal counterpart to [Known Limitations](#known-limitations): sharp
edges in the code itself — traps, divergences, coverage gaps, and deferred work — that
an agent editing this repo will eventually hit. **Divergence labels** (D-N) are the
audit's running register of intentional deviations from the ideal; the ones referenced
across this file are defined inline below.

| Item | Where it bites | Source |
|------|----------------|--------|
| **D-1 (revised)**: `onnxruntime` declared but never imported in `src/` | A search for its usage finds nothing in `src/`, but the declaration is load-bearing: `asr/vad.py:97` loads silero with `onnx=True` (importing `onnxruntime` inside `silero_vad`), and `silero-vad` ≥6 declares it only under its onnx extras. Don't "remove the unused dep." | `pyproject.toml:37`; `asr/CLAUDE.md`; CLAUDE.md |
| **D-3 (closed)**: `kokoro_mlx` import-isolation guard gap | Closed — `test_help_without_models.py` now checks all five engine packages (incl. `kokoro_mlx`) in every guard set, and `test_engine_import_isolation.py` pins `mlx_lm`/`kokoro_mlx` to their single wrapper files. | `tests/integration/test_help_without_models.py`; `tests/unit/asr/test_engine_import_isolation.py:20-27`; CLAUDE.md Trap 2 |
| **D-7**: `ruff check .` fails on committed code | Pre-existing lint findings mean `ruff check .` is **not** a listed passing command; fixing needs code edits, deferred. | CLAUDE.md "Commands"; `pyproject.toml [tool.ruff]` |
| Recording loop can hang on the **final** 4/3/2 attempt | Known v1 bug; interim workaround is Ctrl-C (SIGINT cleans temp files). Underlying fix deferred. | README.md:251–258 |
| LLM and research **agree** on Qwen3-14B at MLX 4-bit (closed divergence; re-quantised down from 6-bit) | The prior Qwen3.5-9B-VLM trap was retired in May 2026; the 6-bit variant of Qwen3-14B exceeded the M3 Pro 18 GB unified-memory budget alongside resident Whisper, so the manifest was re-quantised to 4-bit at the same parameter count (~8 GB on disk, ~9–10 GB resident). The hardware-budget rule is now codified: future LLM swaps MUST sanity-check resident size against ≈10 GB (18 GB − ~5 GB macOS+Python − ~3 GB resident ASR encoder). Don't reintroduce a divergence without a research-doc update. | `installer/manifest.py`; `llm/CLAUDE.md`; `doc/research_llm.md` (Update — 2026-05-25) |
| `torchaudio` capped `<2.9` | Bumping to ≥2.11 moves decode to unbundled `torchcodec` and crashes the first live VAD call; only `-m live_asr` catches it (and it skips when deps absent). | `pyproject.toml:38`; commit `21dfb86`; CLAUDE.md Trap 1 |
| Several `# noqa: BLE001` blanket-except swallows | Debrief audio (`audio_player.py:145,149`), grammar JSON parse (`grammar_analyzer.py:138,170`), and tty drain (`coordinator.py:89`) deliberately swallow exceptions so a session/debrief never hangs — but they also hide real errors. | `rg "noqa: BLE001"` |
| Engine imports tagged `# noqa: PLC0415` | Function-local imports trip the linter's "import at top" rule on purpose; they must stay local (Principle V/VIII). Don't "clean up" by hoisting. | `asr/vad.py:81`, `asr/whisper_mlx_engine.py:77–159` |
| `live_asr` / `repro` tests **skip** instead of fail | `test_vad_live_smoke.py` and the repro gate `importorskip`/`pytest.skip` when deps or the user's own recordings are absent — green CI does **not** mean these ran. | `tests/integration/test_vad_live_smoke.py:21–23`, `repro_gate_test.py:32,95,98` |
| `metrics` imports `speakloop.asr` (types only) | Convenient but a latent Principle-V seam: the dependency must stay types-only and **never** reach `speakloop.llm` or a model package (asserted by comment, not a test). | `metrics/self_corrections.py:1–4`; `metrics/CLAUDE.md` |
| Two-tier tty reads assume a real terminal | Raw `termios`/`cbreak` reads fall back to `input()` for piped/scripted use; subtle to debug when stdin is unusual. | `cli/practice.py:63–175`; `debrief/menu.py` |
| Debrief must **never hang** on TTS/playback failure | A failed clip must still reach the menu (FR-029); the guarantee rests on the blanket-except swallows above, not on a positive test of every failure path. | `debrief/CLAUDE.md`; `audio_player.py:145–149` |

## Known Limitations

Condensed from `README.md` "Known limitations" + "Troubleshooting" (this is v1).

- **Accented technical jargon can still be misheard.** ASR is biased toward each
  question's domain terms, but a strong L1 accent on dense vocabulary can produce wrong
  transcripts. The report's `asr:` block shows exactly what produced the transcript.
  Mitigation: add the terms you use to the question's `tags`/answer wording. (README.md:184–188, 223–231)
- **LLM grammar feedback can fail and degrade to fluency-only.** If Qwen isn't installed
  or errors, the session still completes with fluency metrics + a fluency narrative; the
  report's `phase_c_error` records why (absent = not installed; message = analyzer raised
  it). (README.md:189–192, 211–221)
- **No phoneme-level pronunciation scoring.** You can replay the question/ideal answer
  and hear feedback read aloud, but speakloop does not score pronunciation. (README.md:193–194)
- **Recording loop can hang on the final 4/3/2 attempt.** Known v1 bug; interim fix is
  Ctrl-C (the SIGINT handler cleans partial temp files and exits). Underlying fix
  deferred. (README.md:251–258)
- **Microphone permission (macOS).** First run is blocked until Terminal/iTerm/VS Code is
  granted mic access in System Settings → Privacy & Security → Microphone; `doctor`
  reports status. (README.md:242–249)
- **Model download interruptions** are normal and recoverable: re-run the same command
  (resumable); proxies via `HTTPS_PROXY`/`HF_ENDPOINT`, or copy `~/.speakloop/models/`
  from an unrestricted network. (README.md:200–209)
- **VAD breakage after dependency upgrades.** `silero-vad` (and `torchaudio<2.9`) is
  pinned deliberately; restore with `uv sync` from the committed `uv.lock`. (README.md:233–240)
- **Switching off a personal `~/.speakloop/qa.yaml`** requires deleting/renaming it,
  because the home override wins over the in-repo default. (README.md:260–266)

## Pointer Index

If you want X, read Y.

| If you want… | Read |
|--------------|------|
| The governing rules (the spec that wins on conflict) | `.specify/memory/constitution.md` |
| The architecture map + per-module index | `CLAUDE.md` (root), then `src/speakloop/<module>/CLAUDE.md` |
| The end-to-end practice/debrief loop | `src/speakloop/cli/practice.py`, `src/speakloop/sessions/coordinator.py` |
| The CLI commands, flags, and entry point | `src/speakloop/cli/main.py` |
| The report data model / frontmatter schema | `src/speakloop/feedback/frontmatter.py`, `specs/002-post-session-debrief/contracts/report-frontmatter.yaml` |
| Which models download per phase + the Qwen rationale | `src/speakloop/installer/manifest.py` |
| How an engine is swapped (the Protocols) | `src/speakloop/{asr,tts,llm}/interface.py` |
| ASR engine selection + fallback behavior | `src/speakloop/asr/selection.py` |
| Domain biasing / VAD details | `src/speakloop/asr/domain_context.py`, `src/speakloop/asr/vad.py`, `src/speakloop/asr/seed_lexicon.py` |
| Path/dir resolution + Q&A precedence | `src/speakloop/config/paths.py` |
| The default questions + their YAML shape | `content/questions.yaml`, `src/speakloop/content/schema.py` |
| Why each model was chosen | `doc/research_tts.md`, `doc/research_asr.md`, `doc/research_asr_l2_accent.md`, `doc/research_llm.md`, `doc/research_methodology.md` |
| Per-feature specs/plans/tasks | `specs/001-…` through `specs/005-…` (`spec.md` · `plan.md` · `tasks.md`) |
| Contract / protocol-shape tests | `tests/contract/` (`test_{asr,tts,llm}_interface.py`, `test_report_frontmatter.py`, `test_content_schema.py`, `test_cli_commands.py`) |
| The "`--help` loads no engines" + offline + path-portability guards | `tests/integration/test_help_without_models.py`, `test_offline_after_install.py`, `test_path_portability_audit.py` |
| Live ASR/VAD smoke (run when touching `torchaudio`) | `tests/integration/test_vad_live_smoke.py` (`-m live_asr`) |
| User-facing usage, install, troubleshooting | `README.md` |

## Concrete Examples

Two artifacts lifted from the repo, so the data shapes are not paraphrased.

### A real report frontmatter block

The hand-authored example from the README (a Phase-C report with the additive `asr:`
provenance block and a ranked grammar pattern). Source: `README.md:83–129`.

```yaml
---
schema_version: 1
session_id: 2026-01-15-android-lifecycle-example
started_at: 2026-01-15T09:00:00-08:00
question_id: android-lifecycle-example
question: |
  Walk me through the Activity lifecycle callbacks on a configuration change.
attempts:
  - ordinal: 1
    time_budget_seconds: 240
    actual_duration_seconds: 232
    metrics:
      words_total: 290
      speech_rate_wpm: 92.0
      filler_words_count: 16
      filler_density_per_100_words: 5.5
      pauses_count: 19
      mean_pause_ms: 650
      self_corrections_count: 4
grammar_patterns:
  - label: Missing article before singular noun
    occurrence_count: 3
    impact_rank: 1
    explanation: |
      Persian has no indefinite article, so "a/an" is often dropped before
      English singular count nouns. This is the highest-impact pattern this session.
    evidence:
      - attempt_ordinal: 1
        quote: the system creates new Activity instance
        corrected: the system creates a new Activity instance
    suggested_fix: Add "a/an" before singular count nouns introduced for the first time.
top_priority: |
  Add articles before singular nouns — it appeared 3 times and most affects clarity.
asr:
  engine: whisper-mlx
  model: mlx-community/whisper-large-v3-turbo
  initial_prompt: |
    Android, Activity, lifecycle, onCreate, onDestroy, configuration change.
  initial_prompt_sha256: 1f0c…(truncated)
  vad:
    threshold: 0.5
    min_silence_ms: 300
  fell_back: false
generated_by_phase: C
---
```

### The Python shape of a `Session`

The in-memory typed report returned by `run_session` and rendered by both
`report_builder` and `debrief`. Condensed from `feedback/frontmatter.py:75–104` (nested
`Attempt`, `AttemptMetrics`, `GrammarPattern`, `AsrProvenance` defined above it in the
same file):

```python
@dataclass
class Session:
    session_id: str
    started_at: datetime
    question_id: str
    question_text: str
    attempts: list[Attempt]                                  # always length 3
    grammar_patterns: list[GrammarPattern] = field(default_factory=list)
    generated_by_phase: Literal["A", "B", "C"] = "B"
    # --- Additive top-level keys (002-post-session-debrief) ---
    cross_attempt_narrative: str | None = None               # what improved across rounds
    top_priority: str | None = None                          # the single most-impactful fix
    # --- Additive ASR provenance (003-asr-l2-accent-accuracy) ---
    asr: AsrProvenance | None = None                         # emitted as top-level `asr:`
    phase_c_error: str | None = None                         # set when Phase C degraded to B
```

`SCHEMA_VERSION = 1` is a module constant (`feedback/frontmatter.py:11`); every field
added since v1 is optional and emitted only when present — that is how the schema stays 1.

## Open Questions

Architectural questions worth raising in a brainstorm — derived from the dependency
graph and the friction map, not trivia. The two factual loose ends are kept at the end.

1. **Why do engine modules consume `installer` directly rather than receiving it via DI?**
   `asr`, `tts`, and `llm` each import `installer` to validate/locate models
   (Module Map "Depends on"). That couples every engine wrapper to the installer's
   surface; an injected "model locator" seam would let engines be tested and swapped
   without the installer. Intentional simplicity, or a seam worth extracting?
2. **Is the `metrics` → `asr` "types only" edge a Principle-V leakage risk?**
   `metrics` is meant to be deterministic and engine-free, yet it imports from `asr`
   for transcript types (`metrics/self_corrections.py`). The "types only" rule is held
   by a comment, not a test — should the shared types live in a neutral module so the
   edge can't silently widen?
3. **Is `debrief`'s simultaneous dependency on both `feedback` and `tts` too wide for a
   presentation module?** `debrief` renders the `Session` (`feedback`) *and* reads it
   aloud (`tts`). That is two concerns in one presentation layer; splitting render from
   read-aloud would narrow each consumer's blast radius.
4. **Why is `cli` the only module wiring all others together — composition root or
   accidental hub?** `cli` imports nine modules (Module Map). If that is the intended
   single composition root, it should be named as such; if it's drift, some wiring
   (e.g. engine construction) might belong in `sessions`.
5. **Cold-start load latency of Whisper vs Parakeet vs Qwen** is unmeasured.
   *Resolve by:* timing `ensure_loaded()` / first `generate()` for each engine on the
   target M-series chip and recording the medians.
6. **Phase-C grammar-analysis duration per attempt** is unmeasured.
   *Resolve by:* instrumenting `feedback.grammar_analyzer.analyze` (Qwen `generate` wall
   time) across a representative set of transcripts.
7. **End-to-end median session duration** (playback + 3 attempts + ASR + Phase C +
   debrief) is unmeasured.
   *Resolve by:* logging start/finish timestamps in `sessions.coordinator.run_session`
   over several real sessions and reporting the median.

Factual loose ends:

8. **`interview/` directory purpose.** A top-level `interview/` directory exists but is
   **empty and gitignored** (`.gitignore` line `interview/`); no tracked file documents
   its intended use (matches in `specs/003-*` refer to the interview *concept*, not this
   directory). Appears to be local-only scratch space, but its role is undocumented.
9. **Test counts not independently verified.** The "306 passed, 3 skipped" figure (see
   [Quick Facts](#quick-facts)) is cited from CLAUDE.md, not re-run here; the repo holds
   67 `test_*.py` files across `tests/{unit,contract,integration}/`.
