# Contract — loop.yaml additions

`~/.speakloop/loop.yaml` gains three **additive, optional** keys. Absent or invalid values fall back
to defaults (mirrors existing `LoopConfig` tolerance). Not auto-created. No `schema_version` change
(this is user config, not the report).

```yaml
# existing keys (unchanged)
daily_capacity: 5
warmup_enabled: true
followups_enabled: true

# NEW (011) — all optional
engine: claude            # default analysis engine: local | openrouter | claude  (default: local)
claude_fast_model: haiku  # model alias for the FAST tier (mishearing, drills)    (default: haiku)
claude_strong_model: sonnet  # model alias for the STRONG tier (reasoning calls)  (default: sonnet)
```

| Key | Type | Default | Validation |
|-----|------|---------|------------|
| `engine` | str | `local` | one of `{local, openrouter, claude}`; unknown → fall back to `local` (and an explicit `--engine` always overrides config anyway) |
| `claude_fast_model` | str | `haiku` | any non-empty string (an alias or full model id); blank/invalid → `haiku` |
| `claude_strong_model` | str | `sonnet` | any non-empty string; blank/invalid → `sonnet` |

`LoopConfig` becomes:

```python
@dataclass(frozen=True)
class LoopConfig:
    daily_capacity: int = DEFAULT_DAILY_CAPACITY
    warmup_enabled: bool = True
    followups_enabled: bool = True
    engine: str = "local"            # NEW
    claude_fast_model: str = "haiku"     # NEW
    claude_strong_model: str = "sonnet"  # NEW
```

Set-once example (one line) to make Claude Code the default:

```bash
echo "engine: claude" >> ~/.speakloop/loop.yaml
```
