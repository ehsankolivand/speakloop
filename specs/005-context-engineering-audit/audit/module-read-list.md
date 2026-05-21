# Module-read list + dependency graph (T006) — FR-002, FR-007, FR-034

Each module's `__init__.py` and primary public entry points were read in full. No module
`CLAUDE.md` is rewritten (US2) unless it appears here.

## Per-module verified summary

| Module | Public interface (from `__init__.py`) | Engine boundary owned | Verified |
|--------|----------------------------------------|-----------------------|----------|
| `asr` | `ASREngine`, `Transcript`, `WordTiming`, `TranscriptionContext`, `ASREngineError`, `EngineSelection`, `build_engine` | `mlx_whisper`, `silero_vad`, `parakeet_mlx` | ✅ |
| `audio` | `devices`, `playback` (modules); `recorder.py` | none | ✅ |
| `cli` | `app` (typer) — commands `practice`, `doctor`, `trends` | none | ✅ |
| `config` | `paths` (incl. `resolve_qa_file`) | none | ✅ |
| `content` | `QAFile`, `Question`, `load`, `QALoadError`, `QASchemaError` | none | ✅ |
| `debrief` | `DebriefChoice`, `run` | none (consumes injected `TTSEngine`) | ✅ |
| `feedback` | `frontmatter`, `grammar_analyzer`, `markdown_writer`, `report_builder` (+ `catalog`, `coherence`, `narrative`) | none | ✅ |
| `installer` | `ensure_models`, `manifest`, `InstallDeclinedError`, `InstallFailedError` | none | ✅ |
| `llm` | `LLMEngine`, `LLMEngineError` | `mlx_lm` | ✅ |
| `metrics` | `compute_all` + `fillers`, `pauses`, `self_corrections`, `speech_rate` | none | ✅ |
| `sessions` | `abort`, `coordinator`, `timer` | none | ✅ |
| `trends` | `aggregator`, `reader`, `renderer` | none | ✅ |
| `tts` | `TTSEngine`, `TTSEngineError` (+ `cache`) | `kokoro_mlx` | ✅ |

## Inter-module dependency graph (FR-007)

Scan: `rg -n "^\s*(from|import)\s+speakloop\." src/speakloop/` → per-module edges
(importer → imported, self excluded):

```
asr       -> installer
audio     -> sessions            # NOTE: audio imports sessions (abort) — see below
cli       -> audio, config, content, feedback, installer, llm, sessions, trends, tts
config    -> (none — leaf)
content   -> (none — leaf)
debrief   -> feedback, tts
feedback  -> asr, config, llm
installer -> config
llm       -> installer
metrics   -> asr
sessions  -> asr, audio, config, content, feedback, metrics
trends    -> (none — leaf)
tts       -> config, installer
```

**Leaves (no internal deps):** `config`, `content`, `trends`.
**Top orchestrators:** `cli` (depends on 9 modules) and `sessions` (depends on 6).
**Engine wrappers depend only downward** to `installer`/`config` (model paths), never on each
other — Principle V holds at the module level too.

`audio -> sessions`: `audio` imports `sessions.abort` (the shared abort-flag), the one upward
edge; recorded as INFO divergence D-6 (accurate, not a problem — both are leaf-ish utilities).
