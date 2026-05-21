# Engine-import owner map (T004) — FR-006, SC-L, Principle V

Scan: `rg -n "^\s*(import|from)\s+(mlx_whisper|silero_vad|onnxruntime|parakeet_mlx|mlx_lm|kokoro)" src/speakloop/`

**Result: engine isolation HOLDS.** Each directly-imported engine package is imported
(function-local) in exactly one wrapper file.

| Engine package | Owning file | Import site(s) | Status |
|----------------|-------------|----------------|--------|
| `mlx_whisper` | `src/speakloop/asr/whisper_mlx_engine.py` | lines 78, 102, 118 | ✅ one file |
| `silero_vad` | `src/speakloop/asr/vad.py` | line 81 | ✅ one file |
| `parakeet_mlx` | `src/speakloop/asr/parakeet_engine.py` | line 48 | ✅ one file |
| `mlx_lm` | `src/speakloop/llm/qwen_engine.py` | lines 47, 78, 79 | ✅ one file |
| `kokoro_mlx` | `src/speakloop/tts/kokoro_engine.py` | line 41 | ✅ one file |
| `onnxruntime` | **none (transitive)** | — | ⚠ divergence D-1 |

**D-1 — `onnxruntime`:** declared in `pyproject.toml:30` (`onnxruntime>=1.20`) but there is
**no `import onnxruntime`** anywhere in `src/speakloop/`. The only textual occurrences are a
docstring (`asr/interface.py:6`) and the existing `asr/CLAUDE.md:31`. It is a **transitive**
runtime dependency of `silero_vad` (pinned explicitly to control the resolved version). It is
recorded as transitive-via-silero, NOT as an owned wrapper import. The `asr/CLAUDE.md:31`
wording ("the ONLY file that imports `silero_vad` / `onnxruntime`") is corrected in the asr
rewrite (T028) to say `vad.py` owns `silero_vad`; `onnxruntime` arrives transitively through it.

**D-2 — naming:** the package is `kokoro_mlx` (import) / `kokoro-mlx` (pyproject:18), not
"kokoro". Docs use `kokoro_mlx`.

**Dedicated isolation test:** `tests/unit/asr/test_engine_import_isolation.py` exists and audits
the asr engine packages. `mlx_lm` isolation is exercised indirectly by
`tests/integration/test_help_without_models.py`; `kokoro_mlx` has no dedicated isolation test
(finding D-3, flag-only — no test created here per FR-053).

All engine imports are function-local (`# noqa: PLC0415`) so `speakloop --help` loads no model
packages (Principle VIII).
