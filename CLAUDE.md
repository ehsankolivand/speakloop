<!-- SPECKIT START -->
Active feature: 004-public-release-readiness — make speakloop cloneable & runnable
  by a stranger. Default questions move to a discoverable in-repo
  `content/questions.yaml`; `~/.speakloop/qa.yaml` becomes an opt-in personal
  override (precedence: --qa-file → home override → repo default; no auto-copy).
  Adds a stdlib+git path-portability audit (pytest, < 2 s) that fails on any
  machine-specific absolute path. Rewrites the root README (pitch · platforms ·
  install · quickstart · annotated report example · known limitations ·
  troubleshooting). No new dependency; report schema_version stays 1; MIT LICENSE
  present.

Plan: specs/004-public-release-readiness/plan.md
Spec: specs/004-public-release-readiness/spec.md
Research: specs/004-public-release-readiness/research.md
Data model: specs/004-public-release-readiness/data-model.md
Contracts: specs/004-public-release-readiness/contracts/ (question-resolution · path-audit)
Code touchpoints: src/speakloop/config/paths.py (default_qa_file/resolve_qa_file),
  src/speakloop/cli/practice.py (resolution + FR-006 error), content/questions.yaml
  (migrated), tests/integration/test_path_portability_audit.py (new), README.md.

Prior feature: 003-asr-l2-accent-accuracy — faithful transcripts on Persian-L1
  accented technical English. Default ASR Whisper-large-v3-turbo (mlx-whisper),
  Parakeet-TDT via `--asr-engine parakeet` + automatic fallback; per-session domain
  biasing + Silero-VAD; additive `asr:` frontmatter key (schema_version stays 1).
  Plan: specs/003-asr-l2-accent-accuracy/plan.md · Spec: specs/003-asr-l2-accent-accuracy/spec.md

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
