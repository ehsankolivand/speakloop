# Adversarial-review verdict (T026/T027) — FR-014, SC-C, gate G3

A fresh review sub-agent (Explore agent) was invoked per the research §I protocol — reads ONLY
the top-level `CLAUDE.md` + `src/speakloop/**` + `tests/**` + `pyproject.toml` + the constitution,
independent of the author, classifying each claim CRITICAL/MAJOR/MINOR/INFO against code.

## Iterations

| Pass | Result | Findings | Action |
|------|--------|----------|--------|
| 1 | FAIL | 1 CRITICAL, 1 MINOR — cited `test_help_without_models.py` as the kokoro_mlx guard (it omits kokoro_mlx); implied all wrappers use `# noqa: PLC0415` | reworded trap #2 + conventions to be precise (T027) |
| 2 | FAIL | 1 MAJOR, 1 MINOR — the `# noqa`/`# type: ignore` annotation claim still overstated (kokoro import is bare); test-attribution ambiguous | removed the annotation claim entirely; attributed the assertion to the exact test function `test_importing_cli_loads_no_engine_packages` |
| 3 | **PASS** | **0 CRITICAL, 0 MAJOR** | recorded — gate G3 satisfied |

## Final verdict (pass 3)

`VERDICT: PASS (0 CRITICAL, 0 MAJOR)`

Every claim traced to a `file:line` in code: tech-stack versions vs `pyproject.toml`, all 13
Layout dependency edges vs `from speakloop.` imports, engine-import ownership (mlx_whisper /
silero_vad / parakeet_mlx → asr; mlx_lm → llm; kokoro_mlx → tts), onnxruntime-has-no-direct-import,
the documented commands, all six traps, and the Python 3.12 pin — all verified accurate. The
verdict and the divergence table are the recorded artifact (this file) per SC-C.
