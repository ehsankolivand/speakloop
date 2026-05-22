# Contract: Grammar analysis — model output, generation config, and recovery

**Feature**: 006-feedback-quality-reliability · **Phase**: 1 · **Owner module**: `llm/` (wrapper) + `feedback/grammar_analyzer.py`

This is the seam between the local LLM and the verified report. It pins (A) the JSON the model
must emit, (B) the generation config the wrapper applies, and (C) the recovery ladder. All of
it sits **inside the `llm/` wrapper and the single `grammar_analyzer.py` call site** — no engine
specifics leak past `qwen_engine.py` (Constitution Principle V).

## A. Model output schema (flat — research Axis 2 §4)

```json
{"patterns": [
  {
    "label": "string",
    "occurrence_count": 1,
    "explanation": "string (required only for open-bucket, non-catalog labels)",
    "evidence": [
      {"attempt_ordinal": 1, "quote": "verbatim substring", "corrected": "minimal rewrite"}
    ]
  }
]}
```

- Flat array; **no nested `oneOf`/optional objects** (4-bit Qwen3 drifts on nested schemas — research Axis 2 §4, Recommendation 12).
- `label` SHOULD be drawn from the injected catalog labels; otherwise it is an open-bucket label and `explanation` is required (existing `grammar_analyzer.py` rule V4).
- Prompt demands: double-quoted keys/strings, no trailing commas, no markdown fences, no prose, no `<think>` (existing system prompt; research Axis 2 §4 "no preface, no fence").
- Few-shot: **at most 2 examples** in the system prompt (research Axis 2 §3 — more wastes the 4-bit context budget); add a 3rd only if schema drift is observed.

**Post-conditions (unchanged verification — data-model §1 V1–V5):** every emitted evidence quote
is verified verbatim + coherent; no-op fixes dropped; open-bucket gate applied; deterministic sort.
The model proposes; the deterministic pipeline disposes. This contract MUST NOT relax V1–V5.

## B. Generation config (applied **inside** `qwen_engine.py`)

Vendor non-thinking values from the Qwen3-8B model card (research Axis 1 §1, Recommendations 1–2,5,6,10):

| Param | Value | Was | Source |
|-------|-------|-----|--------|
| `enable_thinking` | `False` | already False ✅ | Qwen3-8B card; grammar = pattern-completion (research Axis 2 §1) |
| `temperature` | `0.7` | **0.2 (wrong)** at call site | Qwen3-8B card "Best Practices" |
| `top_p` | `0.8` | 0.8 ✅ | same |
| `top_k` | `20` | 20 ✅ | same |
| `min_p` | `0.0` | 0.0 ✅ | same |
| `repetition_penalty` | `1.05` | **none** | research Recommendation 5 (mlx-lm default 1.0 = no-op; 4-bit is loop-prone) |
| `repetition_context_size` | `40` | **none** | same (default 20 too small) |
| `stop` | `["<\|im_end\|>"]` | **none** | research Recommendation 10 (defensive EOS) |
| `max_tokens` | ≤ `2048` paragraph-level (≈4× input) | 2048 fixed | research Axis 2 §6, Recommendation 6 |

- Implemented via `make_sampler(...)` + `make_logits_processors(repetition_penalty=…, repetition_context_size=…)` (research "Chat-template invocation"). These are mlx-lm-native — **no new dependency** for sampling/rep-penalty.
- **Call-site change**: remove the `temperature=0.2` override in `grammar_analyzer.analyze(...)`; the wrapper owns the research-aligned defaults.
- **Interface**: `LLMEngine.generate` signature stays stable; if params are surfaced they are **optional with research defaults** (additive, Principle V). The wrapper constructs sampler + logits processors + stop internally.

## C. Recovery ladder (research Axis 3 decision tree — in-process, never persisted)

```
generate() ─▶ strip fences / <think>
   ├─ json.loads(text)                                   → validate → return
   ├─ on JSONDecodeError → json_repair.loads(text)       → validate → return
   ├─ repetition-loop OR finish_reason=="length":
   │     one bounded regenerate (repetition_penalty↑≈1.15, temperature −0.1)
   └─ terminal failure → existing graceful fallback (phase_c_error set, Phase-B report)
```

- **Library**: `json-repair` (PyPI 0.59.10, 2026-05-14 — pure-Python, **zero required runtime deps**, offline-safe; the optional `[schema]` extra is **not** taken — the flat schema does not need Pydantic). It **replaces** the brittle hand-rolled regex repair (`_repair_json`, `_loads_lenient`, optional `json5`) in `grammar_analyzer.py`.
- **New dependency decision** (flagged per spec Assumption): adding `json-repair` is the one new third-party dependency this sprint; justified because it (a) is the research-recommended safety net, (b) removes ~5 brittle regexes ("boring over novel"), (c) directly serves SC-001/SC-004. Offline guarantee preserved.
- Retry is **bounded** (at most one regenerate) so a bad session cannot hang (FR-003).
- On terminal failure the behavior is **exactly today's** (FR-003): `phase_c_error` recorded, Phase-B report rendered, session does not crash.

## Test obligations

- T-G1 prompt emits the flat schema; a golden well-formed response parses with zero repair.
- T-G2 fixtures of known-bad output (single quotes, trailing comma, fenced, junk-token-before-key, truncated) recover via `json-repair` to the same verified patterns (cached fixtures — no live model; Constitution Dev Guidelines).
- T-G3 a repetition-loop fixture triggers exactly one bounded regenerate, then succeeds or falls back cleanly.
- T-G4 the wrapper passes `repetition_penalty`/`repetition_context_size`/`stop`/`enable_thinking=False`; asserted without a live model (monkeypatched `mlx_lm`).
- T-G5 the `--help`/no-model import guard still holds (engine import stays function-local).
