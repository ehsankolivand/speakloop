# Contract: `gate.assess_standalone_safety` (RAM-only standalone variant)

A new function in `pronunciation/gate.py`, alongside the unchanged 016 `assess_safety(engine, …)`.

```python
def assess_standalone_safety(
    *,
    min_free_mb: int,
    available_mb: int | None = None,   # injectable for tests; None → measured via psutil (function-local)
) -> SafetyDecision: ...
```

Returns the **same** `SafetyDecision` dataclass as 016 (`safe`, `reason`, `available_mb`, `engine`).

## Decision logic (RAM-only — no engine penalty)

| Condition | Result | Reason carries |
|---|---|---|
| `available_mb` measured and `≥ min_free_mb` | **SAFE** | "enough free memory for the pronunciation model" |
| `available_mb` unreadable (psutil absent/fails) | **SAFE** (cautious) | a one-line "couldn't read free memory; proceeding" note |
| `available_mb` measured and `< min_free_mb` | **UNSAFE** (low memory) | "Only N MB free; the model needs ~3 GB. Close some apps and retry." (remediation, no "switch engine" hint — there is no engine) |

`engine` field is set to `"standalone"`. The `min_free_mb` reuses `loop.yaml
pronunciation_min_free_mb` (default 4500).

## Difference from the interview gate (must stay distinct)

- `assess_safety("local", …)` → **always UNSAFE** (the resident Qwen feedback model dominates the
  budget). **Unchanged.**
- `assess_standalone_safety(…)` → **never** applies the local-engine penalty (no feedback model is
  resident in `speakloop pronounce`); it only checks live RAM.

This separation is the FR-011 requirement: the standalone variant must not weaken the interview rule.
A test asserts that, with the **same** low/high RAM input, `assess_safety("local", …)` is UNSAFE while
`assess_standalone_safety(…)` follows RAM only.

## Override (unchanged 016 UX)

The CLI (`cli/pronounce.py`) treats UNSAFE exactly like 016: skip by default, print the plain-language
reason, and offer the explicit freeze-warned `[y/N]` override only on an interactive terminal; a
non-interactive run never overrides (skips). SAFE proceeds (no override needed). The model is loaded
ONLY on SAFE or an explicit override (SC-009).

## Invariants

- `psutil` imported function-local; degrades gracefully when absent.
- No network; pure decision (does not load the model — only decides).
