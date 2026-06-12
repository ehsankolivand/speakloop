# Contract: safety gate (`pronunciation/gate.py`)

The heart of the feature (US3 / FR-012..FR-017 / SC-001). Decides whether it is safe to load the
~2–3 GB pronunciation model, from the active feedback engine + live available RAM. Permissive,
lightweight, no network. `psutil` is imported **function-local**; the gate degrades gracefully if it
is unavailable.

## Types

```python
@dataclass(frozen=True)
class SafetyDecision:
    safe: bool
    reason: str            # plain-language English; ALWAYS includes a remediation hint when unsafe
    available_mb: int | None   # measured available RAM, or None if unmeasurable
    engine: str
```

## `assess_safety(engine: str, *, min_free_mb: int, available_mb: int | None = None) -> SafetyDecision`

`available_mb` is injectable for tests; production passes `None` and the gate measures via
`psutil.virtual_memory().available` (function-local import; on ImportError → `available_mb=None`).

Decision table:

| Active engine | Available RAM | Decision | Reason (shape) |
|---|---|---|---|
| `local` | any | **UNSAFE** | "You're using the local Qwen feedback engine; loading the pronunciation model on top of it would likely exceed your machine's memory and freeze it. Switch to a cloud engine (`--engine openrouter`/`--engine claude` or `speakloop setup`) to enable drills." |
| `openrouter`/`claude` | `≥ min_free_mb` | **SAFE** | "Drills are available — your local feedback model isn't resident, so there's room for the pronunciation model." |
| `openrouter`/`claude` | `< min_free_mb` | **UNSAFE** | "Only <N> MB free; the pronunciation model needs ~3 GB. Close some apps and retry, or skip drills this session." |
| `openrouter`/`claude` | unknown (psutil absent) | **SAFE (cautious)** | "Drills are available (couldn't read free memory; proceeding because a cloud engine is active)." |
| unknown engine value | treated as non-local | same as cloud rows | — |

Notes:
- `local` is **always** UNSAFE regardless of the RAM reading — the local feedback model dominates the
  budget and the gate must never risk it (SC-001). This is the single most important rule.
- The threshold default is `4500` MB (`loop.yaml pronunciation_min_free_mb`); model peak ~3 GB +
  headroom. Conservative: borderline machines err toward UNSAFE.
- The gate **only decides**; it never loads the model. The caller (CLI) loads only on SAFE, or on an
  explicit freeze-warned override for UNSAFE.

## Caller contract (CLI, `practice.py`)

```
setting = loop_config.pronunciation_drills            # auto | on | off  (or --drills/--no-drills override)
if setting == "off":            -> no gate, no offer, no load
decision = assess_safety(engine, min_free_mb=cfg.pronunciation_min_free_mb)
if decision.safe:
    if setting == "auto":  offer [Y/n] (decision.reason shown); proceed on yes
    if setting == "on":    proceed without prompt
    -> ensure model present (opt-in download), build scorer, inject into run_session
else:  # unsafe
    print decision.reason (warn + remediation)
    if interactive and setting in (auto,on):
        offer freeze-warned override [y/N] default N: "This may freeze your machine. Load anyway?"
        if yes: ensure model, build scorer, inject
    else: skip drills (no load)
```

`SC-001` test: with `engine="local"` (and/or low RAM), `assess_safety(...).safe is False` and no code
path constructs the scorer under the default setting. The override path is only reachable via an
explicit interactive "yes" to the freeze warning.
