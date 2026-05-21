# Trap-evidence list (T008) — FR-004, FR-011, SC-D (≥5, each evidence-cited)

Each retained trap cites a commit hash, a code/test `file:line`, or a `specs/` reference.

1. **`torchaudio<2.9` pin.** torchaudio≥2.11 moves decoding to the unbundled `torchcodec`,
   crashing the first live VAD call. *Evidence:* `pyproject.toml:29`, `asr/CLAUDE.md:41-44`,
   `live_asr` marker `pyproject.toml:77`, commit `21dfb86` (feat 003).
   → **Trap:** don't bump `torchaudio` without running `uv run pytest -m live_asr`.

2. **Function-local engine imports.** Module-level engine imports break `speakloop --help`
   (Principle VIII). *Evidence:* `tests/integration/test_help_without_models.py`; the
   `# noqa: PLC0415 — function-local` comments in `asr/whisper_mlx_engine.py:78,102,118`,
   `asr/vad.py:81`, etc.
   → **Trap:** keep every engine import (`mlx_whisper`/`silero_vad`/`parakeet_mlx`/`mlx_lm`/
   `kokoro_mlx`) inside the function that uses it, never at module top.

3. **LLM deviates from research on purpose.** The researched `Qwen3.5-9B-MLX-4bit` repo is a
   vision-language model incompatible with `mlx_lm.load()`; the code ships `Qwen3-8B-4bit`.
   *Evidence:* `installer/manifest.py:56-65`, `CLAUDE.md` engine-selection note, commit
   `5757d05`/later.
   → **Trap:** the LLM choice intentionally diverges from `doc/research_llm.md`; don't "fix" it.

4. **Personal-path leakage fails the build.** Sprint-4 added a path-portability audit that
   fails on any machine-specific absolute path. *Evidence:*
   `tests/integration/test_path_portability_audit.py`, `specs/004-public-release-readiness/`,
   commit `28759bc` (feat 004).
   → **Trap:** no `/Users/...` or other absolute personal path in any committed file (this is
   exactly why `doc/research_context_engineering.md:3` had to be sanitized — FR-041).

5. **Q&A file precedence, no auto-copy.** Resolution order is
   `--qa-file / SPEAKLOOP_QA_FILE → ~/.speakloop/qa.yaml → repo-default content/questions.yaml`.
   *Evidence:* `config/paths.py:103` (`resolve_qa_file`), `specs/004-public-release-readiness/`,
   commit `28759bc`.
   → **Trap:** the home file is an opt-in override, not auto-created; don't assume it exists.

6. **`schema_version` stays 1; new frontmatter keys are additive only.** *Evidence:*
   `feedback/frontmatter.py:20,40,91`, constitution Development Guidelines, specs 002/003.
   → **Trap:** never bump `schema_version`; add keys only when present (e.g. `asr:`).

Six evidence-cited traps confirmed (≥5 floor satisfied with one in reserve).
