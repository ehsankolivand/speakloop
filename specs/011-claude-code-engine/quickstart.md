# Quickstart — Claude Code Analysis Engine

## Prerequisites

- Claude Code installed and logged in (`claude auth status` shows `loggedIn: true`).
- A Claude subscription (the calls draw on it; from 2026-06-15 they draw on the separate Agent-SDK
  monthly credit, not your interactive limits).

## Use it for one session

```bash
speakloop practice --engine claude
```

Every analysis step (follow-ups, key points, coverage + content errors, mishearing, consistency,
drill, grammar, coach) runs through your local Claude Code — zero per-token cost.

## Make it the default (set once)

```bash
echo "engine: claude" >> ~/.speakloop/loop.yaml
speakloop practice              # now uses claude with no flag
speakloop practice --engine local   # explicit flag still overrides the config
```

## Tune the model tiers (optional, P2)

```yaml
# ~/.speakloop/loop.yaml
engine: claude
claude_fast_model: haiku     # cheap calls: mishearing classification, drills
claude_strong_model: sonnet  # reasoning calls: coverage, consistency, follow-ups, grammar, coach
```

## Resume a pending session

If Claude Code was unavailable mid-session, the report is saved with `analysis_pending` and the
recordings/transcripts are preserved. Finish it later:

```bash
speakloop resume --engine claude
```

## Check health

```bash
speakloop doctor
```

The "Claude Code" section reports: binary present + path, version, auth state (logged in / org /
subscription), and your configured default engine. If `ANTHROPIC_API_KEY` is set in your
environment, doctor warns that the claude engine strips it to keep billing on your subscription.

## Notes

- **Billing safety**: the engine removes `ANTHROPIC_API_KEY` (and related override vars) from the
  subprocess so calls always bill to your subscription, never pay-per-token.
- **Prompts**: the claude engine reuses the same editable cloud prompt files as the OpenRouter engine
  — `~/.speakloop/openrouter_prompt.txt` (grammar) and `~/.speakloop/openrouter_coach_prompt.txt`
  (coach). (The `openrouter_` name is historical; the claude engine reads the same files so behavior
  matches the cloud engine and no new prompt files are introduced.)
- **Default unchanged**: with no flag and no config, SpeakLoop still uses the offline local Qwen
  engine, byte-identical to before.
- **`--cloud`** still works and is exactly `--engine openrouter`.
