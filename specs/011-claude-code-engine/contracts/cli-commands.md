# Contract — CLI surface

## `practice` and `resume` gain `--engine`

```
speakloop practice --engine {local|openrouter|claude}
speakloop resume   --engine {local|openrouter|claude}
```

- `--cloud` is preserved as an **exact alias** for `--engine openrouter` on both commands.
- Precedence: explicit `--engine`/`--cloud` flag → `loop.yaml` `engine:` → built-in `local`.
- Conflicting `--engine local|claude` together with `--cloud` → error (clear message).
- Unknown `--engine` value → error listing the valid choices.
- `--engine local` / no flag / `engine: local` → **byte-identical** to today's local path.
- `--engine openrouter` / `--cloud` → today's cloud path unchanged.

The resolver lives in one place (a small helper) and is unit-tested over the full precedence matrix.

### Behavior with `--engine claude`

- Builds fast+strong `ClaudeCodeEngine` instances; routes mishearing+drill→fast, the rest→strong.
- Reuses the cloud grammar + coach prompt files (no new prompts).
- Prints a one-time privacy disclosure (transcripts go to Claude Code → Anthropic; audio/reports
  stay local) and a heads-up if the `claude` binary is missing or logged out.
- Always returns a non-None analyzer: if Claude Code is unavailable, every analysis call degrades to
  `analysis_pending` (session still records audio + transcripts + deterministic report; resumable
  via `resume --engine claude`). No auto-fallback to local.

## `doctor` gains a "Claude Code" section (FR-008)

Four rows (plus one informational warning):

| Row | Source (credit-free) | OK / WARN |
|-----|----------------------|-----------|
| CLI binary | `shutil.which("claude")` | OK + path / WARN "not found on PATH" |
| version | `claude --version` | OK + version string / WARN if unreadable |
| auth state | `claude auth status --json` → `loggedIn`/`authMethod`/`subscriptionType` | OK "logged in (claude.ai, max)" / WARN "logged out — run `claude /login`" |
| default engine | `loop_config.load().engine` | OK + `local`/`openrouter`/`claude` |
| (env warning) | `os.environ` has `ANTHROPIC_API_KEY`? | WARN "ANTHROPIC_API_KEY set — claude engine strips it to keep subscription billing" |

- These rows **never FAIL** the doctor exit code (claude is opt-in, like the Cloud section).
- The probe helpers are monkeypatchable; the doctor test injects fakes (no real binary call).
