<!-- SPECKIT START -->
Active feature: 003-asr-l2-accent-accuracy — faithful transcripts on Persian-L1
  accented technical English. Default ASR swaps to Whisper-large-v3-turbo
  (mlx-whisper); Parakeet-TDT kept as `--asr-engine parakeet` flag + automatic
  fallback. Adds per-session domain biasing (initial_prompt) + Silero-VAD
  pre-segmentation; provenance recorded as an additive `asr:` frontmatter key
  (schema_version stays 1).

Plan: specs/003-asr-l2-accent-accuracy/plan.md
Spec: specs/003-asr-l2-accent-accuracy/spec.md
Research (domain mining · VAD thresholds · cross-session model memoization):
  specs/003-asr-l2-accent-accuracy/research.md
Data model (additive asr provenance; TranscriptionContext; SpeechRegion):
  specs/003-asr-l2-accent-accuracy/data-model.md
Contracts: specs/003-asr-l2-accent-accuracy/contracts/
Work stays inside src/speakloop/asr/ (new: whisper_mlx_engine, vad,
  domain_context, selection, seed_lexicon); compass is doc/research_asr_l2_accent.md.

Prior feature: 002-post-session-debrief — educational LLM grammar feedback
  (Persian-L1 catalog) + in-terminal interactive debrief.
  Plan: specs/002-post-session-debrief/plan.md · Spec: specs/002-post-session-debrief/spec.md
  New module: src/speakloop/debrief/ (render + audio + menu).

Base feature: speakloop v1 — local English interview-practice CLI.
  Plan: specs/001-v1-product-spec/plan.md · Spec: specs/001-v1-product-spec/spec.md

Engine selections cite the in-repo research documents:
  doc/research_tts.md (Kokoro-82M),
  doc/research_asr.md (Parakeet-TDT-0.6b-v3),
  doc/research_llm.md (Qwen3-8B 4-bit — deviates from the initial Qwen3.5-9B
    research choice because that HF repo turned out to be a VLM incompatible
    with mlx_lm.load(); see installer/manifest.py rationale comment).

Constitution: .specify/memory/constitution.md (v1.0.0).
Shipping order is three phases (A: listen-only, B: attempts + metrics, C: LLM feedback + trends);
each phase is a complete working system per Principle XII.
<!-- SPECKIT END -->

# speakloop — top-level map

Thirteen fine-grained modules under `src/speakloop/`, single responsibility each,
each with its own `CLAUDE.md` (Constitution Principles IV, XI). Engine-specific
imports live in exactly one file per engine (Principle V).

## Module map

| Module | Responsibility | CLAUDE.md |
|--------|----------------|-----------|
| `config/`     | Filesystem paths & constants                              | [src/speakloop/config/CLAUDE.md](src/speakloop/config/CLAUDE.md) |
| `cli/`        | `typer` app: `practice`, `doctor`, `trends`               | [src/speakloop/cli/CLAUDE.md](src/speakloop/cli/CLAUDE.md) |
| `installer/`  | Model manifest, consent, resumable download, validation   | [src/speakloop/installer/CLAUDE.md](src/speakloop/installer/CLAUDE.md) |
| `content/`    | Q&A YAML loader + schema                                  | [src/speakloop/content/CLAUDE.md](src/speakloop/content/CLAUDE.md) |
| `tts/`        | TTS engine wrapper (Kokoro) + clip cache                  | [src/speakloop/tts/CLAUDE.md](src/speakloop/tts/CLAUDE.md) |
| `audio/`      | Playback, recording, device probing                       | [src/speakloop/audio/CLAUDE.md](src/speakloop/audio/CLAUDE.md) |
| `asr/`        | ASR wrapper — default Whisper-large-v3-turbo (mlx-whisper) + domain biasing + Silero VAD; Parakeet-TDT fallback via `--asr-engine` [Phase B] | [src/speakloop/asr/CLAUDE.md](src/speakloop/asr/CLAUDE.md) |
| `metrics/`    | Fluency metrics                                            | [src/speakloop/metrics/CLAUDE.md](src/speakloop/metrics/CLAUDE.md) |
| `llm/`        | LLM engine wrapper (Qwen3-8B MLX 4-bit) [Phase C]         | [src/speakloop/llm/CLAUDE.md](src/speakloop/llm/CLAUDE.md) |
| `feedback/`   | Frontmatter, atomic writer, report builder, grammar analyzer | [src/speakloop/feedback/CLAUDE.md](src/speakloop/feedback/CLAUDE.md) |
| `debrief/`    | Post-session interactive debrief (render + audio + menu) [Phase C] | [src/speakloop/debrief/CLAUDE.md](src/speakloop/debrief/CLAUDE.md) |
| `sessions/`   | 4/3/2 coordinator, timer, signal handling                 | [src/speakloop/sessions/CLAUDE.md](src/speakloop/sessions/CLAUDE.md) |
| `trends/`     | Cross-session dashboard [Phase C]                         | [src/speakloop/trends/CLAUDE.md](src/speakloop/trends/CLAUDE.md) |
