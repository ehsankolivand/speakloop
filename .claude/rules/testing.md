---
paths: ["tests/**"]
---

# Test rules (owner of rule O9 — specs/014-agent-context-overhaul/research.md)

- Never touch the real `claude` binary, microphone, keyboard, or live models from a
  test. Live model calls are forbidden by the constitution ("Engine tests use cached
  fixtures"); engine tests use small cached WAV/text fixtures committed to the repo.
- `tests/conftest.py` auto-neutralizes the keyboard suite-wide: an autouse
  `_isolate_keyboard` fixture forces `sessions.keyboard.make_key_reader()` to return a
  `NullKeyReader`. Without it, `make_key_reader` probes `/dev/tty` directly
  (`keyboard.py:222`), so running `pytest` from an interactive shell makes the listen
  loop take the real `play_interruptible` audio path and several integration tests fail
  with `PlaybackError` (green in CI/piped, red by hand). Don't undo it; tests needing raw
  behavior inject a `FakeKeyReader` (which overrides the fixture).
- Inject fakes instead:
  - keyboard → `sessions.keyboard.FakeKeyReader` (list-queue or time-gated
    `schedule=`/`clock=` modes) or `NullKeyReader`;
  - Claude Code engine → pass a fake `runner` callable to `ClaudeCodeEngine`
    (`llm/claude_code_engine.py` `__init__`, `runner: Runner = default_runner`) —
    no test spawns a subprocess;
  - recording → inject a fake `record_fn` into the coordinator; never open an
    input stream.
- The byte-identical gate `tests/integration/test_analysis_equivalence.py` must keep
  passing for any change near `sessions/analysis.py` or the coordinator's analysis
  stage; strip the non-deterministic `timings` frontmatter before byte comparisons.
- Two repro gates skip unless local fixtures exist (`tests/integration/
  repro_gate_test.py`, `repro_fresh_5of5_test.py`) — do not "fix" their skips.
- `-m live_asr` tests are deselected by default; run them only when touching
  torchaudio/silero (see root CLAUDE.md Traps).
- `-m live_llm` (`tests/live_llm_test.py`) exercises the REAL local Qwen3-14B-4bit through
  `QwenEngine` — the only default-engine real-model harness. It self-skips when the model is
  absent and is excluded from the default suite (heavy ~8 GB load). Run it explicitly when
  touching `llm/qwen_engine.py` or bumping `mlx_lm`: `uv run pytest -m live_llm`.
- `tests/integration/test_help_without_models.py` and
  `tests/unit/asr/test_engine_import_isolation.py` guard engine-import isolation;
  `tests/integration/test_context_file_budget.py` guards CLAUDE.md line budgets.
