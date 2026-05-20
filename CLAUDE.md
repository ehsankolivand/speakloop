<!-- SPECKIT START -->
Active feature: 002-post-session-debrief — educational LLM grammar feedback
  (Persian-L1 catalog) + in-terminal interactive debrief (rich render + TTS
  read-aloud + replay menu) closing the practice loop.

Plan: specs/002-post-session-debrief/plan.md
Spec: specs/002-post-session-debrief/spec.md
Research (catalog format · impact ranking · rich.live vs rich.markdown):
  specs/002-post-session-debrief/research.md
Data model (additive frontmatter; schema_version stays 1):
  specs/002-post-session-debrief/data-model.md
Contracts: specs/002-post-session-debrief/contracts/
New module: src/speakloop/debrief/ (render + audio + menu).
Catalog/ranking derive from doc/research_methodology.md §1.1/§1.3.

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

Twelve fine-grained modules under `src/speakloop/`, single responsibility each,
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
| `asr/`        | ASR engine wrapper (Parakeet-TDT-0.6b-v3) [Phase B]       | [src/speakloop/asr/CLAUDE.md](src/speakloop/asr/CLAUDE.md) |
| `metrics/`    | Fluency metrics                                            | [src/speakloop/metrics/CLAUDE.md](src/speakloop/metrics/CLAUDE.md) |
| `llm/`        | LLM engine wrapper (Qwen3-8B MLX 4-bit) [Phase C]         | [src/speakloop/llm/CLAUDE.md](src/speakloop/llm/CLAUDE.md) |
| `feedback/`   | Frontmatter, atomic writer, report builder, grammar analyzer | [src/speakloop/feedback/CLAUDE.md](src/speakloop/feedback/CLAUDE.md) |
| `sessions/`   | 4/3/2 coordinator, timer, signal handling                 | [src/speakloop/sessions/CLAUDE.md](src/speakloop/sessions/CLAUDE.md) |
| `trends/`     | Cross-session dashboard [Phase C]                         | [src/speakloop/trends/CLAUDE.md](src/speakloop/trends/CLAUDE.md) |
