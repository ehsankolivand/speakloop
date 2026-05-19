# Phase 0 Research — speakloop v1

**Scope.** This document captures **integration-layer** decisions only. The three model-selection decisions (TTS, ASR, LLM) are already settled by the authoritative research documents under `doc/` and are NOT re-litigated here; this file cites them.

## Engine selections (settled — citations only)

### Decision: TTS engine — **Kokoro-82M** via `kokoro-mlx` / `mlx-audio`

- **Rationale**: Apache 2.0; native MLX on Apple Silicon; highest open-weights TTS ELO (1056) accessible on consumer Macs; Misaki G2P with inline IPA override (`[Hilt](/hˈɪlt/)`) — uniquely valuable for senior-engineering jargon. — `doc/research_tts.md` §TL;DR, §Per-System Deep Dive 1.
- **Alternatives considered (already evaluated in `doc/research_tts.md`)**: Piper (GPL-3.0; lighter setup, deterministic, voice quality a tier lower) — kept as documented failover. Chatterbox (MIT, very natural, but no IPA hook, Python entrypoint finicky). F5-TTS (CC-BY-NC-4.0 weights, license disqualifies commercial use). Orpheus (no native MPS path).
- **Swappability**: the only file that may `import kokoro_mlx` is `src/speakloop/tts/kokoro_engine.py` (Constitution Principle V). The TTS module's public surface is `tts.interface.TTSEngine`.

### Decision: ASR engine — **Parakeet-TDT-0.6b-v3** via `parakeet-mlx`

- **Rationale**: RNN-T/TDT architecture does **not** hallucinate text on silent input — material because interview practice includes thinking pauses; ~2 GB peak RAM fits the 18 GB Mac envelope with headroom; native MLX; word-level timestamps; package actively maintained (v0.5.1, Feb 2026). — `doc/research_asr.md` §TL;DR, §Per-System Deep Dive 1.
- **Alternatives considered**: faster-whisper + whisper-large-v3-turbo (better tooling for hallucination mitigation; needed only if Parakeet stumbles on the user's accent — A/B test deferred). WhisperKit, NeMo PyTorch, Canary-Qwen (too heavy or no Python-from-Mac story).
- **Swappability**: the only file that may `import parakeet_mlx` is `src/speakloop/asr/parakeet_engine.py`. Public surface: `asr.interface.ASREngine`.

### Decision: LLM engine — **Qwen3.5-9B (MLX 4-bit)** via `mlx_lm`

- **Rationale**: Apache 2.0; thinking mode DISABLED by default in the small series (0.8B/2B/4B/9B), which avoids the unfixable `<think>` leak that disqualifies Qwen3-8B across every engine; 262 K context easily fits a full session's transcripts; highest IFBench in the size class. — `doc/research_llm.md` §TL;DR, §Per-Model Deep Dive 1.
- **Alternatives considered**: Llama 3.1 8B (kept as fallback per `doc/research_llm.md`; safer telemetry on M3 Pro). Gemma 3 4B (snappy but less depth for grammar-pattern analysis). Ministral-3-8B (Apple-Silicon-unverified). Phi-4-mini (too verbose).
- **Swappability**: the only file that may `import mlx_lm` is `src/speakloop/llm/qwen_engine.py`. Public surface: `llm.interface.LLMEngine`.

> The Phase 0 research above is **read from `doc/research_tts.md`, `doc/research_asr.md`, `doc/research_llm.md` verbatim**. No further engine research is needed for v1.

---

## Integration-layer decisions (new in this Phase 0)

### Decision: Resumable download primitive — **`huggingface_hub.snapshot_download`**

- **Rationale**: All three chosen engines distribute weights via HuggingFace Hub. `snapshot_download(repo_id=..., resume_download=True, local_dir=...)` provides byte-range resume out of the box (writes `.incomplete` part files), which is exactly the Constitution Principle VI guarantee. No extra wrapper required.
- **Alternatives considered**: `aria2c` external binary (faster, but adds a non-Python runtime dep on every install); rolling our own range-resume over `requests` (more code, no benefit); raw `git-lfs` (no automatic resume).
- **Constraints honored**: FR-021 (byte-range resumable), FR-022 (post-download validation — `snapshot_download` writes `etag` markers that we check in `installer/validator.py`), SC-002 (≤ 1 % re-download).

### Decision: Audio I/O — **`sounddevice` + `soundfile`**

- **Rationale**: `sounddevice` (PortAudio wrapper) is the most widely-used cross-platform Python audio library, exposes both recording (`InputStream`) and playback (`OutputStream`), and integrates cleanly with NumPy arrays. `soundfile` handles WAV write/read. Both have macOS arm64 wheels. The constitution does not name an audio library; this is a Phase-0 choice.
- **Alternatives considered**: `pyaudio` (older, less actively maintained, no arm64 wheels until late 2024); `librosa` (analysis-focused, not a real-time I/O lib); platform-specific (`coreaudio`) bindings (not Pythonic, adds platform code).
- **Where used**: `src/speakloop/audio/playback.py` (Phase A), `src/speakloop/audio/recorder.py` (Phase B), `src/speakloop/audio/devices.py` (doctor input/output enumeration).

### Decision: CLI framework — **`typer`** (paired with `rich`)

- **Rationale**: `typer` is the de-facto modern Python CLI framework, integrates natively with `rich` (already mandated by the constitution for terminal rendering), supports subcommands cleanly (`speakloop practice`, `speakloop trends`, `speakloop doctor`), generates `--help` automatically — satisfies FR-018 (help works without models) trivially because parsing happens before any model load.
- **Alternatives considered**: `argparse` from the standard library (works, but verbose for the 3-subcommand surface and `rich`-rendered help requires hand-rolled formatters); `click` (predecessor to `typer`, fine but more boilerplate).
- **Constraints honored**: FR-018 (`--help` model-free), Constitution Principle I (English help strings — all `typer` strings are English by default), Non-Negotiable Constraint "CLI rendered with `rich`" (typer renders help via `rich`).

### Decision: Q&A configuration format — **YAML** with `PyYAML` (`yaml.safe_load`)

- **Rationale**: Mandated by Constitution Non-Negotiable Constraint ("User configuration: YAML"). `PyYAML` is the standard. `safe_load` (not `load`) is required so user-authored files cannot execute arbitrary Python via tags.
- **Alternatives considered**: None — this is a constitutional constraint.
- **Constraints honored**: FR-027 (starter file in YAML), FR-028 (human-editable YAML), FR-029 (parse errors surfaced with file + line — `yaml.YAMLError.problem_mark.line`).

### Decision: Markdown frontmatter — **emit by hand; parse with `python-frontmatter`**

- **Rationale**: The session-report writer (`feedback/frontmatter.py`) emits YAML frontmatter from a `dataclass` for full control over key order and ASCII safety. The trends reader needs to parse arbitrary user-touched files; `python-frontmatter` (`frontmatter.load(path)`) handles the `--- ... ---` boundary correctly and exposes the body separately.
- **Alternatives considered**: hand-roll the parser for the read path (saves one dep, costs ~30 LOC and a class of edge cases — Windows line endings, escaped triple-dashes); `markdown` library (unnecessary — we only need frontmatter extraction, not rendering).
- **Constraints honored**: FR-015 (Obsidian-compatible), FR-011 (versioned schema), FR-034 (skip malformed files gracefully — `python-frontmatter` raises on bad YAML, which we catch).

### Decision: Atomic Markdown writes — **temp-file-then-`os.replace`**

- **Rationale**: FR-016 requires that Ctrl+C MUST NOT leave a partial report on disk. Writing the entire Markdown string to a `tempfile.NamedTemporaryFile` in the same directory and then `os.replace` to the final filename is the POSIX-atomic move on the same filesystem. Even a Ctrl+C between buffer-flush and rename leaves only the temp file (which `sessions/abort.py` cleans up via signal handler).
- **Alternatives considered**: write-in-place (rejected — partial report possible); `fcntl` advisory locks (no help for the truncation problem); journaled writes (overkill).
- **Constraints honored**: FR-016, SC-005 (0 % aborted sessions leave a report).

### Decision: Testing — **`pytest`** with **committed fixtures**, **no live model calls**

- **Rationale**: Constitution Development Guidelines mandate "Engine tests use cached fixtures. Tests for TTS/ASR/LLM modules use small cached WAV/text fixtures committed to the repo. Live model calls in tests are forbidden." `pytest` is the Python standard; fixtures live under `tests/fixtures/` and are committed (small — only seconds of WAV).
- **Alternatives considered**: `unittest` (older, more boilerplate); record-and-replay HTTP mocks (irrelevant — no HTTP after install).
- **Test boundaries**: Engine wrappers (`tts`, `asr`, `llm`) are unit-tested via dependency-injected mocks that return fixture data; the engine-specific `*_engine.py` files are exercised by a single integration test gated by an environment variable so CI does not call live models.

### Decision: Timer / countdown UX — **`rich.progress`**

- **Rationale**: Already in the dependency tree; renders a live progress bar that doubles as a countdown. Supports `transient=True` so the bar disappears when the attempt ends.
- **Alternatives considered**: hand-rolled ANSI countdown (more code, less consistent with the rest of the UI); `tqdm` (less integrated with `rich`).
- **Where used**: `src/speakloop/sessions/timer.py`.

### Decision: TTS clip cache — **content-addressed by `sha256(voice|text)`** on disk under `~/.speakloop/cache/tts/`

- **Rationale**: FR-004 requires that replay does not re-synthesize. Storing one WAV per `sha256` of the synthesis inputs gives idempotent caching and natural deduplication across questions that share an ideal answer. The cache directory is purgeable without affecting models or sessions.
- **Alternatives considered**: in-memory only (lost on restart — re-synthesis on every run violates the "no re-synthesis on replay" intent of FR-004); SQLite-keyed cache (overkill).

---

## Out-of-scope for Phase 0 (deferred to design Phase 1)

- Concrete fluency-metric definitions (speech rate, pause distribution, filler density, self-correction count) and their numeric thresholds — depend on `doc/research_methodology.md`, which is not yet authored. See `plan.md` § Complexity Tracking. Phase 1 `data-model.md` documents the metric *shape* (names, types, units) but not the numeric thresholds.

- L1-transfer grammar-pattern catalog — also from `doc/research_methodology.md`. `feedback/grammar_analyzer.py` is structurally specified in Phase 1, but the prompt that drives the LLM analysis depends on the methodology doc.

## Resolved NEEDS-CLARIFICATION markers

None — the spec was authored with zero `[NEEDS CLARIFICATION]` markers.
